(() => {
  const toggle = document.getElementById('menuToggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggle && sidebar) toggle.addEventListener('click', () => sidebar.classList.toggle('open'));

  document.querySelectorAll('.flash-close').forEach(button => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });

  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      const message = form.getAttribute('data-confirm');
      if (message && !window.confirm(message)) event.preventDefault();
    });
  });

  const search = document.getElementById('tableSearch');
  const table = document.getElementById('recordsTable');
  const emptySearch = document.getElementById('emptySearch');
  if (search && table) {
    search.addEventListener('input', () => {
      const term = search.value.trim().toLowerCase();
      let visible = 0;
      table.querySelectorAll('tbody tr').forEach(row => {
        const match = row.innerText.toLowerCase().includes(term);
        row.hidden = !match;
        if (match) visible++;
      });
      if (emptySearch) emptySearch.hidden = visible !== 0;
    });
  }
})();
