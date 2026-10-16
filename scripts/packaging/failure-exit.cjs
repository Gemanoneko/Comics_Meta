'use strict';
// Exit-status seam for programmatic electron-builder entries.
// Pinned temp-file 3.4.0 registers async-exit-hook 2.0.1 when the builder first
// creates its temp root. That hook's beforeExit handler finishes the vendor's
// asynchronous temp cleanup and then calls process.exit(0), which overwrote the
// failed entry's exitCode=1 in actual23 (Node exit 0 after a logged builder
// error). This is upstream's own CLI fix (electron-builder cli-util.js,
// issues/2940), verbatim: Node's exit() re-reads exitCode after 'exit' listeners
// run, so the failure code survives while vendor cleanup still runs.
// Called on failure paths only.
function retainFailureExit(proc=process){
  proc.exitCode=1;
  proc.on('exit',()=>{proc.exitCode=1;});
}
module.exports={retainFailureExit};
