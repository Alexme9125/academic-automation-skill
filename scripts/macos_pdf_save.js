/* JXA, executed by osascript, NOT injected into a page or run by Node.
 * One attempt only. Python journals the attempt before starting this process.
 * Exported predicates are exercised with offline fixtures on every platform.
 */
function unique(rows, predicate, reason) {
  var hits = rows.filter(predicate);
  if (hits.length !== 1) throw new Error(reason);
  return hits[0];
}
function labelled(row, labels) {
  return labels.indexOf(row.name) >= 0 || labels.indexOf(row.description) >= 0;
}
function downloadButton(rows) {
  ['sidenavToggle', 'pageSelector', 'print'].forEach(function(id) {
    unique(rows, function(r) { return r.id === id; }, 'PDF_VIEWER_NOT_IDENTIFIED');
  });
  // Google Drive also has id=save. Chrome's Downloads toolbar is a checkbox.
  return unique(rows, function(r) {
    return r.role === 'AXButton' && r.id === 'save' && r.enabled &&
      labelled(r, ['Download', '下载', '下載']);
  }, 'PDF_DOWNLOAD_BUTTON_NOT_UNIQUE');
}
function saveControls(rows) {
  return {
    filename: unique(rows, function(r) { return r.role === 'AXTextField' &&
      labelled(r, ['Save As:', 'Save As', '存储为：', '存储为:', '儲存為：', '儲存為:']); }, 'SAVE_FILENAME_NOT_IDENTIFIED'),
    folder: unique(rows, function(r) { return r.role === 'AXPopUpButton' &&
      labelled(r, ['Where:', 'Where', '位置：', '位置:', '位置']); }, 'SAVE_FOLDER_NOT_IDENTIFIED'),
    save: unique(rows, function(r) { return r.role === 'AXButton' && r.enabled &&
      labelled(r, ['Save', '存储', '儲存']); }, 'SAVE_BUTTON_NOT_IDENTIFIED'),
    cancel: unique(rows, function(r) { return r.role === 'AXButton' &&
      labelled(r, ['Cancel', '取消']); }, 'SAVE_CANCEL_NOT_IDENTIFIED')
  };
}
function checkDestination(controls, filename, folder) {
  if (controls.filename.value !== filename || controls.folder.value !== folder)
    throw new Error('SAVE_DESTINATION_CHANGED');
}

function run(argv) {
  ObjC.import('Foundation');
  var phase = 'preflight', events = [], process, enhanced, changed = false;
  try {
    var content = $.NSString.stringWithContentsOfFileEncodingError(argv[0], $.NSUTF8StringEncoding, null);
    var request = JSON.parse(ObjC.unwrap(content));
    var chrome = Application('Google Chrome'), system = Application('System Events');
    if (!chrome.running()) throw new Error('CHROME_NOT_RUNNING');
    process = system.processes.byName('Google Chrome');
    function plainURL(url) { return String(url).split('#')[0]; }
    function guard(requireFront) {
      var windows = chrome.windows();
      if (!windows.length || String(windows[0].id()) !== String(request.window))
        throw new Error('BOUND_WINDOW_NOT_FRONT');
      var tab = windows[0].activeTab();
      if (String(tab.id()) !== String(request.tab) || plainURL(tab.url()) !== plainURL(request.url))
        throw new Error('BOUND_PDF_TAB_CHANGED');
      if (requireFront && !process.frontmost()) throw new Error('CHROME_FOCUS_CHANGED');
      var ax = process.windows();
      // Browser id plus active tab and AX title bind the native sheet to this PDF.
      if (!ax.length || ax[0].name() !== windows[0].name() + ' - Google Chrome')
        throw new Error('NATIVE_WINDOW_NOT_IDENTIFIED');
      return ax[0];
    }
    var window = guard(false);
    if (window.sheets().length) throw new Error('EXISTING_DIALOG_REQUIRES_USER');
    if (chrome.execute(chrome.windows()[0].activeTab(), {javascript: 'document.contentType'}) !== 'application/pdf')
      throw new Error('PAGE_IS_NOT_PDF');
    chrome.activate();
    delay(0.25);
    window = guard(true);
    enhanced = process.attributes.byName('AXEnhancedUserInterface').value();
    if (enhanced !== true) {
      process.attributes.byName('AXEnhancedUserInterface').value = true;
      changed = true;
    }
    function attr(e, name) { try { return e.attributes.byName(name).value(); } catch (_) { return ''; } }
    function rows(root, max, stopAtMore) {
      var elements = root.entireContents(), result = [];
      // Read toolbar controls only; do not collect article text or link contents.
      for (var i = 0; i < elements.length && i < max; i++) {
        var e = elements[i], role = e.role();
        if (['AXButton','AXTextField','AXPopUpButton'].indexOf(role) < 0) continue;
        var row = {element:e, role:role, id:attr(e,'AXDOMIdentifier'),
          name:e.name(), description:e.description(), enabled:e.enabled(), value:attr(e,'AXValue')};
        result.push(row);
        if (stopAtMore && row.id === 'more' && result.some(function(r) { return r.id === 'pageSelector'; })) break;
      }
      return result;
    }
    var download;
    for (var attempt = 0; attempt < 4; attempt++) {
      window = guard(true);
      if (window.sheets().length) throw new Error('UNEXPECTED_DIALOG');
      try { download = downloadButton(rows(window, 180, true)); break; }
      catch (error) { if (attempt === 3) throw error; delay(0.5); }
    }
    guard(true);
    phase = 'download_clicked'; events.push(phase);
    system.click(download.element);
    function waitFor(predicate, reason) {
      for (var n = 0; n < 30; n++) {
        window = guard(true);
        if (predicate(window)) return;
        delay(0.2);
      }
      throw new Error(reason);
    }
    waitFor(function(w) { return w.sheets().length === 1; }, 'SAVE_DIALOG_NOT_OPENED');
    var sheet = window.sheets()[0];
    if (sheet.sheets().length) throw new Error('UNEXPECTED_NESTED_DIALOG');
    var controls = saveControls(rows(sheet, 150, false));
    phase = 'save_dialog'; events.push(phase);
    controls.filename.element.value = request.filename;
    if (controls.filename.element.value() !== request.filename) throw new Error('FILENAME_NOT_SET');
    guard(true);
    if (window.sheets().length !== 1 || window.sheets()[0].sheets().length)
      throw new Error('SAVE_DIALOG_CHANGED');
    saveControls(rows(window.sheets()[0], 150, false));
    // This shortcut is sent only to the positively identified Save sheet.
    system.keystroke('g', {using:['command down','shift down']});
    waitFor(function(w) { return w.sheets().length === 1 && w.sheets()[0].sheets().length === 1; }, 'GO_TO_FOLDER_NOT_OPENED');
    phase = 'go_to_folder'; events.push(phase);
    sheet = window.sheets()[0];
    var nested = sheet.sheets()[0];
    var folder = unique(rows(nested, 120, false), function(r) { return r.role === 'AXTextField'; }, 'GO_TO_FOLDER_FIELD_NOT_UNIQUE');
    folder.element.value = request.folder;
    folder.element.focused = true;
    window = guard(true);
    if (window.sheets().length !== 1 || window.sheets()[0].sheets().length !== 1)
      throw new Error('GO_TO_FOLDER_CHANGED');
    folder = unique(rows(window.sheets()[0].sheets()[0], 120, false), function(r) { return r.role === 'AXTextField'; }, 'GO_TO_FOLDER_FIELD_NOT_UNIQUE');
    if (folder.element.value() !== request.folder || !folder.element.focused()) throw new Error('FOLDER_INPUT_NOT_CONFIRMED');
    // Return is restricted to the nested folder sheet that we just opened.
    system.keyCode(36);
    waitFor(function(w) { return w.sheets().length === 1 && w.sheets()[0].sheets().length === 0; }, 'GO_TO_FOLDER_NOT_ACCEPTED');
    sheet = window.sheets()[0];
    controls = saveControls(rows(sheet, 150, false));
    checkDestination(controls, request.filename, request.folder.split('/').pop());
    if ($.NSFileManager.defaultManager.fileExistsAtPath(request.folder + '/' + request.filename))
      throw new Error('SAVE_TARGET_ALREADY_EXISTS');
    guard(true);
    phase = 'save_clicked'; events.push(phase);
    system.click(controls.save.element);
    // No more UI input after Save: closing sheets can temporarily change the AX
    // window list. Python proves completion from the stable file, not the UI.
    // In particular, never confirm a Replace/overwrite dialog.
    return JSON.stringify({status:'save_requested', phase:phase, events:events});
  } catch (error) {
    return JSON.stringify({status:'needs_user', phase:phase, events:events, error:String(error)});
  } finally {
    if (changed) {
      try { process.attributes.byName('AXEnhancedUserInterface').value = enhanced; } catch (_) {}
    }
  }
}
if (typeof module !== 'undefined') module.exports = {downloadButton:downloadButton, saveControls:saveControls, checkDestination:checkDestination};
