// Playwright-side action: click once, keep page handlers and capture its download.
async page => {
  const selector = __SELECTOR__, capture = __CAPTURE__;
  const observed = [], popups = [], listeners = [];
  let resolveDownload, first = false;
  const arrived = new Promise(resolve => { resolveDownload = resolve; });
  const watch = p => {
    const handler = download => {
      observed.push({name:download.suggestedFilename(), url:download.url()});
      if (!first) { first = true; resolveDownload(download); }
    };
    p.on('download', handler);
    listeners.push([p, handler]);
  };
  const popup = p => { popups.push(p); watch(p); };
  watch(page);
  page.on('popup', popup);
  let clickError = '', result;
  try {
    try {
      await page.locator(selector).click({timeout:8000, noWaitAfter:true});
    } catch (e) {
      // A click can commit before a redirect destroys its context. Never click twice.
      clickError = String(e.message || e);
    }
    const download = await Promise.race([
      arrived, page.waitForTimeout(__EVENT_TIMEOUT__).then(() => null)
    ]);
    result = {status:download ? 'download_event' : 'no_event', observed:observed,
      click_error:clickError, page_url:page.url(), popup_urls:popups.map(p => p.url())};
    if (download) {
      try {
        await download.saveAs(capture);
        result.saved = true;
        result.suggested_filename = download.suggestedFilename();
        result.download_url = download.url();
      } catch (e) {
        result.saved = false;
        result.save_error = String(e.message || e);
      }
    }
    return result;
  } finally {
    page.off('popup', popup);
    for (const [p, listener] of listeners) p.off('download', listener);
  }
}
