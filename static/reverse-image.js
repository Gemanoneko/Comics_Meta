// Reverse-image results supplement the trusted metadata lookup.
const imagePanel=document.createElement('section');
imagePanel.className='panel';
imagePanel.innerHTML='<h3>Identify by cover</h3><p>Search the cover when the title is ambiguous or an edition is missing. Only the selected image is uploaded to TinEye when configured.</p><div class="flex"><select id="coverChoice" aria-label="Archive image"><option value="0">First image</option><option value="1">Second image</option><option value="2">Third image</option><option value="3">Fourth image</option><option value="4">Fifth image</option></select><a id="coverDownload" download="comic-cover.jpg">Download selected cover</a><a href="https://lens.google/" target="_blank" rel="noopener noreferrer">Open Google Lens</a><button id="reverseLookup">Search image automatically</button></div><p id="reverseMessage" aria-live="polite"></p><div id="reverseResults"></div>';
$('candidates').before(imagePanel);
function imageChoice(){if(!selected)return;const url='/api/cover?id='+selected.id+'&index='+$('coverChoice').value;$('localCover').src=url;$('coverDownload').href=url}
const reviewBeforeImages=review;
review=function(row){reviewBeforeImages(row);$('coverChoice').value='0';$('reverseResults').replaceChildren();$('reverseMessage').textContent='For a free search, download the cover and upload it in Google Lens. Automatic search requires a configured TinEye account.';imageChoice()};
$('coverChoice').onchange=imageChoice;
async function reverseFallback(){
 if(!selected)return;
 $('reverseLookup').disabled=true;$('reverseMessage').textContent='Searching the selected cover…';
 try{
  const result=await request('reverse-image',{comic:selected.id,index:Number($('coverChoice').value)});
  $('reverseMessage').textContent=result.matches.length?result.notice+(result.cached?' Cached result.':''):'No cover match found. This does not mean the comic is unknown.';
  $('reverseResults').replaceChildren(...result.matches.map(match=>{
   const row=node('p');const link=node('a',match.title);link.href=match.url;link.target='_blank';link.rel='noopener noreferrer';row.append(link);
   if(match.comicvine_issue){const button=node('button','Check identified issue');button.onclick=()=>preview({id:match.comicvine_issue});row.append(document.createTextNode(' '),button)}
   return row;
  }));
 }catch(e){$('reverseMessage').textContent=e.message}
 finally{$('reverseLookup').disabled=false}
}
$('reverseLookup').onclick=reverseFallback;
// A title search with no candidates falls back to the image adapter.
const searchBeforeImages=search;
search=async function(){await searchBeforeImages();if($('lookupMessage').textContent.startsWith('No series found.'))await reverseFallback()};
$('lookup').onclick=search;
