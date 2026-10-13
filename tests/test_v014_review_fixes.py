"""Regression cases from v0.1.4 review; fixtures never touch the live catalog."""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import imprints
import local_model
import pilot_credits
import problems
import provenance
from test_worker import scratch_directory


class ReviewFixTests(unittest.TestCase):
    def test_fraction_parse_preserves_leading_zero(self):
        for value,number in [('0.5','0.5'),('00.5','0.5'),('001.5','1.5'),('000','0'),('001A','1A')]:
            self.assertEqual(app.parse_name('Example '+value+'.cbz')[1],number)

    def test_catalog_fraction_refresh_once_and_only_matching_old_parse(self):
        with scratch_directory() as directory,patch.object(app,'DATA',Path(directory)):
            with app.db() as con:
                con.execute('DELETE FROM catalog_migrations')
                for path,number in [('Example 0.5.cbz','.5'),('Example 1.5.cbz','.5'),('Other 0.5.cbz','5')]:
                    con.execute('INSERT INTO comics(path,number,metadata) VALUES(?,?,?)',(path,number,'{"Number":"human"}'))
            with app.db() as con:
                rows=con.execute('SELECT path,number,metadata FROM comics ORDER BY id').fetchall()
                self.assertEqual([r['number'] for r in rows],['0.5','.5','5'])
                self.assertTrue(all(r['metadata']=='{"Number":"human"}' for r in rows))
                con.execute("UPDATE comics SET number='.5' WHERE id=1")
            with app.db() as con:self.assertEqual(con.execute('SELECT number FROM comics WHERE id=1').fetchone()[0],'.5')

    def test_publisher_aliases_and_imprint_pilot(self):
        for canonical,aliases in imprints.PUBLISHER_ALIASES.items():
            for alias in aliases:self.assertFalse(provenance.disagrees('Publisher',canonical,alias))
        self.assertEqual(pilot_credits.compare('Publisher','Image Comics','Skybound'),'agree')
        self.assertEqual(pilot_credits.compare('Publisher','Unknown A','Unknown B'),'disagree')

    def test_date_aware_imprints_with_unknown_year(self):
        for year,parent in [('1998','Image Comics'),('1999','DC Comics')]:
            self.assertEqual(imprints.split({'Publisher':'WildStorm','Year':year})['Publisher'],parent)
        self.assertEqual(imprints.split({'Publisher':'Archaia','Year':'2012'}),{'Publisher':'Archaia','Year':'2012'})
        self.assertEqual(imprints.split({'Publisher':'Archaia','Year':'2013'})['Publisher'],'BOOM! Studios')
        for value in ('WildStorm','Archaia'):
            self.assertEqual(imprints.split({'Publisher':value,'Series':'Example'}),{'Series':'Example'})

    def test_imprint_guard_uses_retained_publisher_and_year(self):
        fields,_,_=automatic.external_plan({'Publisher':'Dark Horse Comics'},{'Publisher':'Skybound'}, {},True)
        self.assertNotIn('Imprint',fields)
        fields,_,_=automatic.external_plan({'Publisher':'Image Comics','Year':'1998'},
                                         {'Publisher':'WildStorm','Year':'2020'}, {},True)
        self.assertEqual(fields,{'Imprint':'WildStorm'})
        fields,_,_=automatic.external_plan({'Publisher':'DC Comics'},{'Publisher':'WildStorm'}, {},True)
        self.assertNotIn('Imprint',fields)

    def test_case_punctuation_kept_but_real_title_and_accent_difference_replace(self):
        for a,b in [('AMAZING SPIDER-MAN','Amazing Spider-Man'),('Batman - Year One','Batman: Year One')]:
            self.assertFalse(provenance.disagrees('Series',a,b))
        for a,b in [('Batman','Batman Year One'),('Asterix','Astérix')]:
            self.assertTrue(provenance.disagrees('Series',a,b))

    def test_counts_cache_scans_once_until_catalog_commit(self):
        with scratch_directory() as directory,patch.object(app,'DATA',Path(directory)):
            cache=problems.CountsCache()
            try:
                with patch.object(problems,'counts',wraps=problems.counts) as scan:
                    first=cache.get('');self.assertEqual(cache.get(''),first)
                    self.assertEqual(scan.call_count,1)
                    with app.db() as con:
                        con.execute("INSERT INTO comics(path,size,mtime,status) VALUES('Example.cbz',1,1,'missing')")
                        record={'signature':[1,1],'outcome':'write_failed'}
                        con.execute('INSERT INTO discovery_records(path,value) VALUES(?,?)',('Example.cbz',json.dumps(record)))
                    self.assertEqual(cache.get('')['write_failed'],1)
                    self.assertEqual(scan.call_count,2)
                    self.assertEqual(cache.get('')['write_failed'],1)
                    self.assertEqual(scan.call_count,2)
            finally:cache.close()

    def test_progress_files_close_and_reconfiguration_release_catalog(self):
        import progress_snapshot
        with scratch_directory() as directory:
            root=Path(directory);first=root/'first';second=root/'second';first.mkdir();second.mkdir()
            with patch.object(app,'DATA',first),progress_snapshot.Files() as files:
                files.problem_counts.get('')
                with patch.object(app,'DATA',second):files.problem_counts.get('')
                # Reconfiguration closes the old connection, so Windows permits removal.
                (first/'catalog.sqlite').unlink()
            (second/'catalog.sqlite').unlink()  # Public Files.close closes its active connection.

    def test_discarded_direct_collector_releases_owned_connection(self):
        import progress_snapshot
        with scratch_directory() as directory,patch.object(app,'DATA',Path(directory)):
            files=progress_snapshot.Files();files.problem_counts.get('')
            del files
            (Path(directory)/'catalog.sqlite').unlink()

    def test_credits_reject_timeout_and_overlong_text(self):
        with patch.object(local_model,'credits_pages',return_value=(['image'],['page'])):
            self.assertIsNone(local_model.read_credits('fixture',ask=lambda *a,**k:{'indicia':'x'*4001,'credits':''}))
            self.assertIsNone(local_model.read_credits('fixture',ask=lambda *a,**k:(_ for _ in ()).throw(TimeoutError())))
            good={'indicia':'Published by Image Comics','credits':''}
            self.assertEqual(local_model.read_credits('fixture',ask=lambda *a,**k:good)['indicia'],good['indicia'])

    def test_credits_transport_caps_tokens_time_and_bytes(self):
        response=json.dumps({'message':{'content':'{"indicia":"","credits":""}'}}).encode()
        with patch.object(local_model,'credits_response',return_value=response) as request,patch('pause_control.requested',return_value=False):
            local_model.chat('test',schema=local_model.CREDITS_SCHEMA)
            body=json.loads(request.call_args.args[0].data)
            self.assertEqual(body['options']['num_predict'],local_model.CREDITS_TOKENS)
        with patch.object(local_model,'credits_response',return_value=b'x'*(local_model.CREDITS_BYTES+1)):
            with self.assertRaises(ValueError):local_model.model_reply(None,local_model.CREDITS_SCHEMA)

    def test_credits_watchdog_shuts_held_socket_for_trickling_read(self):
        import threading
        import time
        from unittest.mock import Mock
        stopped=threading.Event();sock=Mock()
        sock.shutdown.side_effect=lambda *a:stopped.set()
        response=Mock(status=200)
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        def trickle(limit):
            # Continuous input cannot renew the total deadline as it could a socket timeout.
            while not stopped.wait(.005):pass
            return b'{}'
        response.read.side_effect=trickle
        connection=Mock();connection.getresponse.return_value=response
        request=local_model.urllib.request.Request('http://127.0.0.1:11434/api/chat',data=b'{}')
        with patch.object(local_model,'CREDITS_SECONDS',.05),patch.object(local_model.socket,'create_connection',return_value=sock),patch.object(local_model.http.client,'HTTPConnection',return_value=connection):
            started=time.monotonic()
            with self.assertRaises(TimeoutError):local_model.credits_response(request)
            self.assertLess(time.monotonic()-started,1)
            self.assertTrue(stopped.is_set())
            sock.shutdown.assert_called_with(local_model.socket.SHUT_RDWR)
