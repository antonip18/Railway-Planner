'use strict';
// One component handles every journey leg; no duplicated direct/one-transfer/two-transfer code.
for (const root of document.querySelectorAll('.stock-view')) {
  const stock = JSON.parse(root.dataset.stock),
    tabs = root.querySelector('.wagon-tabs');
  const grid = root.querySelector('.wagon-grid'),
    caption = root.querySelector('.wagon-caption');

  function render(carriage, index) {
    caption.textContent = `Wagon ${index+1} · ${carriage.name} · skład źródłowy: ${carriage.source_train}`;
    grid.replaceChildren();
    grid.style.gridTemplateColumns = `repeat(${carriage.rows}, 34px)`;
    grid.style.gridTemplateRows = `repeat(${carriage.columns}, 34px)`;
    for (const element of carriage.elements) {
      const node = document.createElement('div');
      node.className = 'static-element';
      node.textContent = element.nazwa;
      node.style.gridColumn = `${element.rzad_od} / ${element.rzad_do+1}`;
      node.style.gridRow = `${element.kolumna_od} / ${element.kolumna_do+1}`;
      grid.append(node);
    }
    for (const seat of carriage.seats) {
      const node = document.createElement('div');
      node.className = 'seat';
      if (seat.czy_dla_niepelnosprawnych) node.classList.add('prm');
      else if (seat.czy_dla_rowerzystow) node.classList.add('bike');
      else if (seat.czy_przy_stoliku) node.classList.add('table-seat');
      node.textContent = seat.numer;
      node.title = `Miejsce ${seat.numer} · ${seat.lokalizacja || 'standard'}`;
      node.style.gridColumn = String(seat.rzad);
      node.style.gridRow = String(seat.kolumna);
      grid.append(node);
    }
    [...tabs.children].forEach((tab, i) => {
      tab.classList.toggle('active', i === index);
      tab.setAttribute('aria-pressed', String(i === index));
    });
  }
  stock.forEach((carriage, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${index+1} · ${carriage.source_train}`;
    button.addEventListener('click', () => render(carriage, index));
    tabs.append(button);
  });
  if (stock.length) render(stock[0], 0);
}
