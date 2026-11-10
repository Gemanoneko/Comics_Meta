// Data-only publication preparation. Sully runs the existing publisher separately.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {digest,requireThat,writeJson} from './common.mjs';
import {strictBuildReceipt} from './build-receipt.mjs';
import {strictQAReceipt} from './qa-receipt.mjs';

export function createPromotion(config) {
  const {receipt:build,artifacts}=strictBuildReceipt(config.build);
  requireThat(build.sourceHead===config.sourceHead&&build.sourceIdentity===config.sourceIdentity&&build.version===config.version,'Promotion/build identity mismatch');
  const qa=strictQAReceipt({...config.qa,artifacts});
  requireThat(qa.sourceHead===build.sourceHead&&qa.sourceIdentity===build.sourceIdentity&&qa.version===build.version,'Promotion/installed-QA identity mismatch');
  const root=path.resolve(config.outputRoot);requireThat(!fs.existsSync(root),'Fresh promotion output required');
  requireThat(path.basename(config.evidenceRoot).startsWith('illuminati-cmo-publish-')&&!fs.existsSync(config.evidenceRoot),'Fresh publisher evidence target required');
  for(const [file,sha] of [[config.ghExecutable,config.ghSha256],[config.nodeExecutable,config.nodeSha256],[config.cleanupScript,config.cleanupScriptSha256],[config.releaseNotes.path,config.releaseNotes.sha256]])
    requireThat(path.isAbsolute(file)&&digest(fs.readFileSync(file))===sha,'Promotion runtime/notes/cleanup byte drift');
  requireThat(fs.statSync(config.ghConfigDirectory).isDirectory(),'Existing authenticated gh configuration directory required');
  fs.mkdirSync(root);
  const buildPath=path.join(root,'build-receipt.json'),qaPath=path.join(root,'qa-receipt.json');writeJson(buildPath,build);writeJson(qaPath,qa);
  const promotion={schema:1,repository:'Gemanoneko/Comics_Meta',version:config.version,sourceHead:build.sourceHead,sourceIdentity:build.sourceIdentity,
    buildReceipt:{path:buildPath,sha256:digest(fs.readFileSync(buildPath))},qaReceipt:{path:qaPath,sha256:digest(fs.readFileSync(qaPath))},
    artifactRoot:config.build.artifactRoot,artifacts,qaReport:config.qa.qaReport,codeReview:config.qa.codeReview,
    evidenceRoot:config.evidenceRoot,ghExecutable:config.ghExecutable,ghSha256:config.ghSha256,
    nodeExecutable:config.nodeExecutable,nodeSha256:config.nodeSha256,ghConfigDirectory:config.ghConfigDirectory,
    releaseNotes:config.releaseNotes,cleanupScriptSha256:config.cleanupScriptSha256};
  const file=path.join(root,'promotion.json');writeJson(file,promotion);
  return {path:file,sha256:digest(fs.readFileSync(file)),sourceHead:promotion.sourceHead,artifacts};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  requireThat(process.argv.length===4&&/^[a-f0-9]{64}$/.test(process.argv[3]),'Exact reviewed promotion configuration/hash required');
  const raw=fs.readFileSync(process.argv[2]);requireThat(digest(raw)===process.argv[3],'Promotion configuration changed');
  console.log(JSON.stringify(createPromotion(JSON.parse(raw))));
}
