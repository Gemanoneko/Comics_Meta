// Optional cover preview; automatic identity research runs in the browser worker.
const imagePanel=document.createElement('section');
imagePanel.className='panel';
imagePanel.innerHTML='<h3>Identify by cover</h3><p>Download the cover, then search it in Google Lens.</p><div class="flex"><select id="coverChoice" aria-label="Archive image"><option value="0">First image</option><option value="1">Second image</option><option value="2">Third image</option><option value="3">Fourth image</option><option value="4">Fifth image</option></select><a id="coverDownload" download="comic-cover.jpg">Download selected cover</a><a href="https://lens.google/" target="_blank" rel="noopener noreferrer">Open Google Lens</a></div>';
$('candidates').before(imagePanel);
function imageChoice(){if(!selected)return;const url='/api/cover?id='+selected.id+'&index='+$('coverChoice').value;$('localCover').src=url;$('coverDownload').href=url}
const reviewBeforeImages=review;
review=function(row){reviewBeforeImages(row);$('coverChoice').value='0';imageChoice()};
$('coverChoice').onchange=imageChoice;
