(function(){
  var ta=document.querySelector('textarea.textarea-major');
  if(!ta)return 'notarea';
  var setter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
  if(setter&&setter.set)setter.set.call(ta,__EXPR__);
  else ta.value=__EXPR__;
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
  var btn=document.querySelector('input.btn-search');
  if(!btn)return 'nobtn';
  btn.click();
  return 'searched';
})()
