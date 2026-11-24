const material = document.querySelector('.materials');
if (material) {
  const sample = material.querySelector('#trial-sample');
  const draft = material.querySelector('#trial-input');
  sample.addEventListener('change', () => {
    if (sample.value === 'custom') {
      draft.open = true;
      draft.querySelector('input').focus();
    }
  });
  material.addEventListener('submit', () => {
    material.querySelector('#pending').textContent = '称量计算中…';
  });
}
