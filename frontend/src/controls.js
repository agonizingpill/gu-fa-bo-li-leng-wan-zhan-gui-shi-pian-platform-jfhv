import {awaitCompute, request} from './api.js';
import {el, display} from './dom.js';
import {COMPUTE_STATES, evidence} from './store.js';
import {status} from './widgets.js';

const fallback = field => field.kind === 'token' ? evidence.get() : field.initial;
function input(field) {
  if (field.kind === 'bool') return el('select', {name:field.name},
    el('option',{value:'true', selected:fallback(field) === true ? '' : undefined},'是'),
    el('option',{value:'false', selected:fallback(field) === false ? '' : undefined},'否'));
  if (field.kind === 'json') return el('textarea', {name:field.name, required:''}, JSON.stringify(fallback(field), null, 2));
  const numeric = ['int','float'].includes(field.kind);
  return el('input',{name:field.name, required:'', type:numeric ? 'number' : 'text',
    step:field.kind === 'float' ? 'any' : undefined, value:fallback(field) ?? ''});
}
function parse(form, fields) {
  const data = new FormData(form);
  return Object.fromEntries(fields.map(field => {
    const raw = data.get(field.name);
    const convert = ['int','float'].includes(field.kind) ? Number :
      ['bool','json'].includes(field.kind) ? JSON.parse : String;
    return [field.name, convert(raw)];
  }));
}
export function actionForm(action, refresh) {
  const notice = status('');
  const button = el('button', {type:'submit'}, action.label);
  const form = el('form', {class:'action', id:action.name},
    el('h3',{},action.label), el('p',{},action.help),
    el('div',{class:'fields'},action.fields.map(field => el('label',{},
      el('span',{},field.label), input(field)))),
    button, notice);
  form.addEventListener('submit',async event => {
    event.preventDefault();
    button.disabled = true;
    notice.className = 'status';
    try {
      const payload = parse(form, action.fields);
      const data = action.method === 'get'
        ? await request(`${action.path}/${encodeURIComponent(payload[action.keyField])}${action.suffix ?? ''}`)
        : await request(action.path, payload);
      if (data.token && data.status === 'queued') {
        evidence.save(data.token);
        const result = await awaitCompute(data.token, current => {
          notice.textContent = COMPUTE_STATES[current.status] || current.status;
        });
        if (result.status === 'rejected') throw new Error(result.detail);
        notice.textContent = '任务 ' + data.token + ' · ' + display(result.result);
      } else {
        const shown = Array.isArray(data)
          ? data.length ? data.map(display).join('；') : '暂无记录'
          : display(data.code ?? data.status ?? data);
        notice.textContent = (action.success ? action.success + ' · ' : '') + shown;
      }
      notice.classList.add('ok');
      await refresh();
    } catch (error) {
      notice.textContent = error.message;
      notice.classList.add('error');
    } finally { button.disabled = false; }
  });
  return form;
}
