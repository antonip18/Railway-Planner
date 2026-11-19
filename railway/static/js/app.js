'use strict';
// Event delegation keeps dynamically added timetable rows functional.
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.matches('[data-swap]')) {
    const a = document.querySelector('[name=start]'),
      b = document.querySelector('[name=end]');
    [a.value, b.value] = [b.value, a.value];
  }
  if (button.matches('[data-add-stop]')) {
    const rows = document.getElementById('stop-rows');
    const row = rows.firstElementChild.cloneNode(true);
    row.querySelectorAll('input').forEach(input => {
      input.value = '';
    });
    rows.append(row);
  }
  if (button.matches('[data-remove-row]')) {
    const rows = document.getElementById('stop-rows');
    if (rows.children.length > 2) button.closest('tr').remove();
  }
  if (button.matches('[data-add-carriage]')) {
    const rows = document.getElementById('carriage-rows');
    rows.append(rows.firstElementChild.cloneNode(true));
  }
  if (button.matches('[data-remove-carriage]')) {
    const rows = document.getElementById('carriage-rows');
    if (rows.children.length > 1) button.closest('.carriage-input').remove();
  }
});
document.addEventListener('submit', event => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});
