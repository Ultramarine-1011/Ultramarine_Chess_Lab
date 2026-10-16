import {Chessboard, COLOR, INPUT_EVENT_TYPE} from './vendor/cm-chessboard/src/Chessboard.js';
import {Markers, MARKER_TYPE} from './vendor/cm-chessboard/src/extensions/markers/Markers.js';
import {PromotionDialog, PROMOTION_DIALOG_RESULT_TYPE} from './vendor/cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js';

const $ = id => document.getElementById(id);
let board;
let state = null;
let busy = true;
let promoting = false;
const endings = {CHECKMATE: '将死', STALEMATE: '逼和', INSUFFICIENT_MATERIAL: '子力不足',
  FIFTY_MOVES: '五十步规则', THREEFOLD_REPETITION: '三次重复',
  SEVENTYFIVE_MOVES: '七十五步规则', FIVEFOLD_REPETITION: '五次重复'};

function error(message = '') {
  $('error').textContent = message;
  $('error').hidden = !message;
}
async function request(path, data) {
  const response = await fetch(`/api/${path}`, data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...data, revision: state.revision})
  });
  const body = await response.json();
  if (!response.ok) {
    if (body.state) state = body.state;
    throw new Error(body.error || '请求失败');
  }
  return body;
}
function history() {
  const fragment = document.createDocumentFragment();
  let row;
  for (const move of state.moves) {
    if (move.color === 'white' || !row) {
      row = document.createElement('tr');
      for (const text of [move.number, '', '']) {
        const cell = document.createElement('td');
        cell.textContent = text;
        row.append(cell);
      }
      fragment.append(row);
    }
    row.children[move.color === 'white' ? 1 : 2].textContent = move.san;
  }
  $('history').replaceChildren(fragment);
  $('empty-history').hidden = state.moves.length > 0;
  $('history-scroll').scrollTop = $('history-scroll').scrollHeight;
}
function lastMove() {
  board.removeMarkers(MARKER_TYPE.square);
  const move = state?.moves.at(-1)?.uci;
  if (move) {
    board.addMarker(MARKER_TYPE.square, move.slice(0, 2));
    board.addMarker(MARKER_TYPE.square, move.slice(2, 4));
  }
}
function controls() {
  const locked = busy || promoting || !state;
  for (const control of $('settings').elements) control.disabled = locked;
  $('undo').disabled = locked || !state?.can_undo;
  $('submit-move').disabled = locked || state?.engine_turn || state?.result !== '*';
  $('uci-move').disabled = $('submit-move').disabled;
  $('retry').disabled = locked;
}
function render() {
  if (!state) { controls(); return; }
  const orientation = state.config.color === 'white' ? COLOR.white : COLOR.black;
  if (!board || board.getOrientation() !== orientation) {
    // A new game may finish before the component's queued turn animation.
    // Construct the new orientation directly, without racing that queue.
    board?.destroy();
    board = new Chessboard($('board'), {
      orientation, position: state.fen, assetsUrl: '/vendor/cm-chessboard/assets/',
      style: {animationDuration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 160},
      extensions: [{class: Markers}, {class: PromotionDialog, props: {language: 'en'}}]
    });
  }
  board.disableMoveInput();
  board.setPosition(state.fen, false);
  board.removeMarkers();
  lastMove();
  if (!busy && !promoting && !state.engine_turn && state.result === '*') {
    board.enableMoveInput(input, state.config.color === 'white' ? COLOR.white : COLOR.black);
  }
  $('top-dot').className = `side-dot ${state.config.color === 'white' ? 'black' : 'white'}`;
  $('bottom-dot').className = `side-dot ${state.config.color}`;
  $('top-detail').textContent = `${state.config.evaluator} · ${state.config.seconds} 秒/步`;
  $('top-detail').title = JSON.stringify(state.identity);
  $('human-color').textContent = state.config.color === 'white' ? '执白' : '执黑';
  $('move-count').textContent = `第 ${state.fen.split(' ')[5]} 回合`;
  $('result').textContent = state.result;
  $('turn-label').textContent = state.result !== '*' ? '对局结束' : state.engine_turn ? 'UCL 行棋' : '你的回合';
  let text = state.engine_turn ? 'UCL 正在思考…' : `轮到你了${state.check ? ' · 你的王被将军' : ' · 点击或拖动棋子落子'}`;
  if (state.result !== '*') {
    const winner = state.result === '1/2-1/2' ? '和棋' :
      ((state.result === '1-0') === (state.config.color === 'white') ? '你获胜' : 'UCL 获胜');
    text = `${winner} · ${endings[state.termination] || state.termination} · ${state.result}`;
  }
  $('status').textContent = text;
  $('status-indicator').className = `status-indicator ${state.result !== '*' ? 'ended' : state.engine_turn ? 'thinking' : ''}`;
  controls();
  history();
}
function readSettings() {
  const form = new FormData($('settings'));
  return {color: form.get('color'), evaluator: form.get('evaluator'),
    seconds: Number(form.get('seconds')), model: form.get('model') || ''};
}
function syncSettings() {
  $('settings').elements.color.value = state.config.color;
  $('seconds').value = state.config.seconds;
  $('evaluator').value = state.config.evaluator;
  $('model').value = state.config.model;
  $('model-field').hidden = state.config.evaluator !== 'Linear';
  $('model').required = state.config.evaluator === 'Linear';
}
async function act(action, data = {}) {
  if (busy || promoting) return;
  busy = true;
  error();
  $('retry').hidden = true;
  render();
  try {
    state = await request(action, data);
    if (action === 'new') syncSettings();
    render();
    if (state.engine_turn) {
      state = await request('engine', {});
    }
    $('uci-move').value = '';
  } catch (exc) {
    error(exc.message || '连接中断，请刷新页面重连。');
    $('retry').hidden = !state?.engine_turn;
  } finally {
    busy = false;
    render();
    if (state?.engine_turn && !$('error').hidden) $('status').textContent = '引擎暂停 · 可重试、悔棋或开始新对局';
  }
}
function input(event) {
  if (event.type === INPUT_EVENT_TYPE.moveInputStarted) {
    if (busy || promoting) return false;
    const moves = state.legal_moves.filter(move => move.startsWith(event.squareFrom));
    board.removeMarkers(MARKER_TYPE.dot);
    for (const square of new Set(moves.map(move => move.slice(2, 4)))) board.addMarker(MARKER_TYPE.dot, square);
    return moves.length > 0;
  }
  if (event.type === INPUT_EVENT_TYPE.moveInputFinished) {
    board.removeMarkers(MARKER_TYPE.dot);
    return;
  }
  if (event.type !== INPUT_EVENT_TYPE.validateMoveInput) return;
  const prefix = event.squareFrom + event.squareTo;
  const moves = state.legal_moves.filter(move => move.startsWith(prefix));
  if (!moves.length) { error('这个目标格不可落子，请选择标记的合法格。'); return false; }
  // The component resets its input before the asynchronous, server-authorized move.
  queueMicrotask(() => {
    if (moves[0].length === 5) {
      promoting = true;
      controls();
      board.showPromotionDialog(event.squareTo, state.config.color === 'white' ? COLOR.white : COLOR.black, choice => {
        promoting = false;
        if (choice.type === PROMOTION_DIALOG_RESULT_TYPE.pieceSelected) {
          queueMicrotask(() => act('move', {move: prefix + choice.piece.charAt(1)}));
        } else { render(); }
      });
    } else { act('move', {move: prefix}); }
  });
  return false;
}
$('settings').addEventListener('submit', event => { event.preventDefault(); const config = readSettings(); act('new', config); });
$('evaluator').addEventListener('change', () => {
  const linear = $('evaluator').value === 'Linear';
  $('model-field').hidden = !linear;
  $('model').required = linear;
});
$('undo').addEventListener('click', () => act('undo'));
$('retry').addEventListener('click', () => act('engine'));
$('move-form').addEventListener('submit', event => {
  event.preventDefault(); act('move', {move: $('uci-move').value.trim().toLowerCase()});
});
try {
  state = await request('state');
  syncSettings();
  busy = false;
  render();
  if (state.engine_turn) await act('engine');
} catch (exc) {
  error(`无法连接本地引擎：${exc.message}。请确认服务正在运行后刷新页面。`);
  $('status').textContent = '连接失败';
}
