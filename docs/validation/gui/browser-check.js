// Run in the local GUI page with agent-browser eval --stdin, or DevTools.
(async () => {
  const $ = id => document.getElementById(id);
  const wait = async condition => {
    const deadline = Date.now() + 10000;
    while (!condition()) {
      if (Date.now() > deadline) throw new Error('GUI did not settle');
      await new Promise(resolve => setTimeout(resolve, 20));
    }
  };
  const start = async color => {
    await wait(() => !$('new-game').disabled);
    $('settings').elements.color.value = color;
    $('seconds').value = '0.01';
    $('evaluator').value = 'Handcrafted';
    $('evaluator').dispatchEvent(new Event('change'));
    $('settings').requestSubmit();
    await wait(() => !$('new-game').disabled);
    if (!$('error').hidden) throw new Error($('error').textContent);
    const state = await (await fetch('/api/state')).json();
    if (state.config.color !== color || state.engine_turn) throw new Error('Wrong player turn');
    const h8 = Number(document.querySelector('.board [data-square="h8"]').getAttribute('y'));
    const a1 = Number(document.querySelector('.board [data-square="a1"]').getAttribute('y'));
    if ((h8 > a1) !== (color === 'black')) throw new Error('Wrong board orientation: ' + color);
    return state;
  };
  // Exercise switching faster than the component's former queued flip.
  for (const color of ['black', 'white', 'black', 'white', 'black', 'white']) await start(color);
  // Real UCL depth-2 White moves against the GUI's real 0.01-second Black.
  const moves = ['b1c3','g1f3','a2a4','d2d4','a4b5','b2b3','a1a8','d1c2','a8b8',
    'c3b5','b8c8','c2c6','d4d5','f3d4','f2f3','f3f4','c8d8','d5e6','c6d5'];
  for (const move of moves) {
    $('uci-move').value = move;
    $('move-form').requestSubmit();
    await wait(() => !$('new-game').disabled);
    if (!$('error').hidden) throw new Error($('error').textContent);
  }
  const state = await (await fetch('/api/state')).json();
  if (state.moves.length !== 37 || state.termination !== 'CHECKMATE' || state.result !== '1-0') {
    throw new Error('Complete game failed: ' + JSON.stringify(state));
  }
  $('undo').click();
  await wait(() => !$('new-game').disabled);
  if ($('result').textContent !== '*') throw new Error('Cannot undo terminal move');
  return {orientationSwitches: 6, plies: state.moves.length, result: state.result,
    termination: state.termination, terminalUndo: true};
})()
