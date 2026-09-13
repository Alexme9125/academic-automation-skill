// One trusted click. Bring only the bound task page forward; never replay a click.
async page => {
  const selector = __SELECTOR__, capture = __CAPTURE__;
  await page.bringToFront();
  const preflight = JSON.parse(await page.evaluate(__PROBE__));
  const blocked = preflight.captcha || preflight.login ? 'needs_verification'
    : preflight.consent ? 'needs_consent' : preflight.visibility !== 'visible' ? 'needs_foreground' : '';
  if (blocked) return {status:blocked, click_attempted:false, preflight, page_url:page.url()};
  try {
    await page.locator(selector).click({trial:true, timeout:8000});
  } catch (e) {
    return {status:'needs_control', click_attempted:false, preflight, page_url:page.url(), click_error:String(e.message || e)};
  }
  const observed = [], popups = [], listeners = [], watched = new Set();
  let resolveDownload, first = false;
  const arrived = new Promise(resolve => { resolveDownload = resolve; });
  const watch = p => {
    if (watched.has(p)) return;
    watched.add(p);
    const handler = async download => {
      // Context page events arrive earlier than popup events. Ignore unrelated tabs.
      if (p !== page && await p.opener().catch(() => null) !== page) return;
      observed.push({name:download.suggestedFilename(), url:download.url()});
      if (!first) { first = true; resolveDownload(download); }
    };
    p.on('download', handler);
    listeners.push([p, handler]);
  };
  const popup = p => { if (!popups.includes(p)) popups.push(p); watch(p); };
  const context = page.context();
  const contextPage = p => { watch(p); };
  watch(page);
  page.on('popup', popup);
  context.on('page', contextPage);
  let clickError = '', result;
  try {
    try {
      await page.locator(selector).click({timeout:8000, noWaitAfter:true});
    } catch (e) {
      // The action can commit before a redirect destroys its context.
      clickError = String(e.message || e);
    }
    const download = await Promise.race([
      arrived, page.waitForTimeout(__EVENT_TIMEOUT__).then(() => null)
    ]);
    result = {status:download ? 'download_event' : 'no_event', observed,
      click_attempted:true, click_error:clickError, page_url:page.url(),
      popup_urls:popups.map(p => p.url()), preflight};
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
    context.off('page', contextPage);
    for (const [p, listener] of listeners) p.off('download', listener);
  }
}
