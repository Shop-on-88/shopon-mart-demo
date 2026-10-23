// 관광공사 사진갤러리(phoko)를 브라우저로 열어 검색 결과가 오는 내부 요청과 화면을 기록한다.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  fs.mkdirSync('tools/probe', { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 1600 } });
  const log = [];
  p.on('response', async (r) => {
    const ct = r.headers()['content-type'] || '';
    if (ct.includes('json') || r.request().resourceType() === 'xhr' || r.request().resourceType() === 'fetch') {
      let body = '';
      try { body = (await r.text()).slice(0, 3000); } catch (e) {}
      log.push({ url: r.url(), method: r.request().method(), post: r.request().postData(), status: r.status(), ct, body });
    }
  });
  await p.goto('https://phoko.visitkorea.or.kr/media/mediaList.kto?keyword=' + encodeURIComponent('축서사'), { waitUntil: 'networkidle', timeout: 60000 }).catch(e => console.log('goto', e.message));
  await p.waitForTimeout(4000);
  await p.screenshot({ path: 'tools/probe/phoko.png' });
  fs.writeFileSync('tools/probe/phoko-net.json', JSON.stringify(log, null, 1));
  fs.writeFileSync('tools/probe/phoko-dom.html', await p.content());
  await b.close();
})();
