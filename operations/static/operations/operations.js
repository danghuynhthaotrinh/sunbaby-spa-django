(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = value => new Intl.NumberFormat('vi-VN').format(value) + ' ₫';
  const integer = value => /^\d+$/.test(String(value)) && Number.isSafeInteger(Number(value));
  function error(input, target, message) {
    if (target) target.textContent = message;
    if (input) input.setAttribute('aria-invalid', message ? 'true' : 'false');
    return !message;
  }
  function notify(message) {
    const el = $('#network-message');
    el.textContent = message; el.hidden = false;
    window.setTimeout(() => {el.hidden = true;}, 6500);
  }
  $$('[data-dismiss-toast]').forEach(button => button.addEventListener('click', () => button.closest('.toast').remove()));
  const search = $('#linen-search');
  if (search) search.addEventListener('input', () => {
    const term = search.value.trim().toLocaleLowerCase('vi'); let count = 0;
    $$('[data-linen-row]').forEach(row => {
      const match = row.dataset.search.toLocaleLowerCase('vi').includes(term);
      row.hidden = !match; if (match) count++;
    });
    $('#no-linen-match').hidden = count > 0;
    $('#linen-result-count').textContent = count + ' loại đồ vải';
  });

  const send = $('#send-form');
  if (send) {
    const linen = JSON.parse($('#linen-data').textContent);
    const byId = new Map(linen.map(x => [String(x.id), x]));
    const active = () => $$('[data-send-row]', send).filter(row => !$('input[name$="-DELETE"]', row).checked);
    const field = name => $(`[name="${name}"]`, send);
    function validateSend(showErrors = true) {
      let valid = true, total = 0;
      const headerMessages = {
        supplier: 'Vui lòng chọn xưởng giặt.', responsible: 'Vui lòng chọn người phụ trách.',
        sent_at: 'Vui lòng chọn ngày giờ giao và hạn nhận.',
        expected_at: 'Vui lòng chọn ngày giờ giao và hạn nhận.'
      };
      for (const [name, text] of Object.entries(headerMessages)) {
        const input = field(name); let msg = input.value ? '' : text;
        if (name === 'expected_at' && input.value && field('sent_at').value && new Date(input.value) <= new Date(field('sent_at').value)) msg = 'Hạn nhận phải sau ngày giờ giao.';
        if (msg) valid = false;
        error(input, $(`[data-header-error="${name}"]`, send), showErrors ? msg : '');
      }
      const rows = active();
      const counts = new Map();
      rows.forEach(row => {const id = $('select', row).value; if (id) counts.set(id, (counts.get(id) || 0) + 1);});
      rows.forEach(row => {
        const select = $('select', row), qty = $('input[name$="-sent_qty"]', row);
        const record = byId.get(select.value);
        $('.available-dirty', row).textContent = record ? record.dirty_qty : '—';
        let itemMsg = !record ? 'Vui lòng chọn loại đồ vải.' : (counts.get(select.value) > 1 ? 'SKU đã có ở dòng khác.' : '');
        let qtyMsg = !integer(qty.value) || Number(qty.value) <= 0 ? 'Nhập số nguyên lớn hơn 0.' : '';
        if (!qtyMsg && record && Number(qty.value) > record.dirty_qty) qtyMsg = `Vượt số đồ bẩn hiện có (${record.dirty_qty}).`;
        if (itemMsg || qtyMsg) valid = false;
        error(select, $('[data-line-error="item"]', row), showErrors ? itemMsg : '');
        error(qty, $('[data-line-error="sent_qty"]', row), showErrors ? qtyMsg : '');
        if (integer(qty.value) && Number(qty.value) > 0) total += Number(qty.value);
      });
      $('#no-send-lines').hidden = rows.length > 0;
      $('#send-total').textContent = total;
      $('#send-cost').textContent = money(total * 5000);
      $('#send-submit').disabled = !valid || !rows.length || !linen.length;
      $('#add-send-line').disabled = rows.length >= linen.length || $$('[data-send-row]', send).length >= 200;
      return valid && rows.length > 0;
    }
    $('#send-lines').addEventListener('change', event => {
      const row = event.target.closest('[data-send-row]'); if (!row) return;
      if (event.target.matches('select')) {
        const record = byId.get(event.target.value);
        $('input[name$="-dirty_qty_snapshot"]', row).value = record ? record.dirty_qty : '';
        $('.snapshot-error', row).textContent = '';
      }
      validateSend();
    });
    send.addEventListener('input', () => validateSend());
    send.addEventListener('change', () => validateSend());
    $('#send-lines').addEventListener('click', event => {
      const button = event.target.closest('[data-remove-line]'); if (!button) return;
      const row = button.closest('[data-send-row]');
      $('input[name$="-DELETE"]', row).checked = true; row.hidden = true;
      validateSend();
    });
    $('#add-send-line').addEventListener('click', () => {
      const management = $('#id_send-TOTAL_FORMS'); const index = Number(management.value);
      if (index >= 200) return;
      const fragment = document.createElement('template');
      fragment.innerHTML = $('#send-empty-row').innerHTML.replace(/__prefix__/g, index);
      const row = $('[data-send-row]', fragment.content);
      const chosen = new Set(active().map(r => $('select', r).value));
      const next = linen.find(x => !chosen.has(String(x.id)));
      if (next) {
        $('select', row).value = next.id;
        $('input[name$="-dirty_qty_snapshot"]', row).value = next.dirty_qty;
      }
      $('input[name$="-sent_qty"]', row).value = '1';
      $('#send-lines').append(fragment.content); management.value = index + 1;
      validateSend(); $('select', row).focus();
    });
    send.addEventListener('submit', event => {
      if (!validateSend()) {event.preventDefault(); return;}
      $('#send-submit').disabled = true; $('#send-submit').textContent = 'Đang xác nhận…';
    });
    // A clean first render stays quiet. Bound errors remain visible after a failed POST.
    const hasServerErrors = $$('.field-error', send).some(el => el.textContent.trim());
    validateSend(hasServerErrors);
  }

  const dialog = $('#shipment-dialog');
  let opener = null, busy = false;
  function closeDialog() {
    if (busy) return;
    dialog.close(); dialog.innerHTML = '';
    if (opener && document.contains(opener)) opener.focus();
  }
  function validateReceive() {
    const form = $('#receive-form', dialog); if (!form) return true;
    let valid = true, missing = 0;
    const date = $('[name="received_at"]', form);
    const dateMsg = date.value ? '' : 'Vui lòng chọn ngày giờ nhận.';
    if (!error(date, $('#receive-date-error', form), dateMsg)) valid = false;
    $$('[data-receive-row]', form).forEach(row => {
      const qty = $('input[name$="-received_qty"]', row), note = $('input[name$="-loss_note"]', row);
      const min = Number(row.dataset.previous), max = Number(row.dataset.sent);
      const quantityOK = integer(qty.value) && Number(qty.value) >= min && Number(qty.value) <= max;
      const qtyMsg = quantityOK ? '' : `Nhập số nguyên từ ${min} đến ${max}.`;
      const gap = quantityOK ? max - Number(qty.value) : 0;
      let noteMsg = gap > 0 && !note.value.trim() ? 'Cần ghi chú khi có thất thoát.' : '';
      if ([...note.value].length > 250) noteMsg = 'Ghi chú thất thoát tối đa 250 ký tự.';
      if (!error(qty, $('[data-receive-error="qty"]', row), qtyMsg)) valid = false;
      if (!error(note, $('[data-receive-error="note"]', row), noteMsg)) valid = false;
      $('.receive-missing', row).textContent = quantityOK ? gap : '—';
      row.classList.toggle('shortage', gap > 0); missing += gap;
    });
    const status = $('#reconciliation-status', form);
    status.className = 'alert ' + (missing > 0 || !valid ? 'bad' : 'good');
    status.textContent = missing > 0
      ? `CẢNH BÁO LỆCH: thiếu ${missing} cái - cần xử lý đền bù với xưởng giặt · Dự kiến: Nhận một phần`
      : (valid ? 'Đối soát khớp · Dự kiến: Đã hoàn tất' : 'Vui lòng kiểm tra lại thông tin nhận hàng.');
    $('#receive-submit', form).disabled = !valid || busy;
    return valid;
  }
  document.addEventListener('click', async event => {
    const link = event.target.closest('[data-open-shipment]'); if (!link || event.ctrlKey || event.metaKey) return;
    event.preventDefault(); opener = link;
    try {
      const response = await fetch(link.href, {headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'});
      if (response.redirected) {window.location.assign(response.url); return;}
      if (!response.ok) throw new Error('Không mở được chi tiết phiếu. Vui lòng tải lại trang.');
      dialog.innerHTML = await response.text(); dialog.showModal(); validateReceive();
    } catch (err) {notify(err.message || 'Không kết nối được máy chủ.');}
  });
  dialog.addEventListener('click', event => {
    if (event.target.closest('[data-close-dialog]')) closeDialog();
    if (event.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closeDialog();
    }
  });
  dialog.addEventListener('cancel', event => {event.preventDefault(); closeDialog();});
  dialog.addEventListener('input', () => validateReceive());
  dialog.addEventListener('change', () => validateReceive());
  dialog.addEventListener('submit', async event => {
    const form = event.target.closest('#receive-form'); if (!form) return;
    event.preventDefault(); if (busy || !validateReceive()) return;
    busy = true;
    const submit = $('#receive-submit', form); submit.disabled = true; submit.textContent = 'Đang ghi nhận…';
    $$('[data-close-dialog]', dialog).forEach(b => b.disabled = true);
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form),
        headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'});
      if (response.redirected) {window.location.assign(response.url); return;}
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        const data = await response.json();
        if (response.ok && data.redirect) {window.location.assign(data.redirect); return;}
        throw new Error(data.error || 'Không thể lưu phiếu. Vui lòng mở lại chi tiết.');
      }
      if (response.status === 422) {
        dialog.innerHTML = await response.text(); busy = false; validateReceive();
      } else throw new Error('Không lưu được phiếu. Hãy kiểm tra kết nối và mở lại chi tiết trước khi thử lại.');
    } catch (err) {notify(err.message || 'Không kết nối được máy chủ.');}
    finally {
      busy = false;
      const current = $('#receive-submit', dialog);
      if (current) {current.textContent = 'Xác nhận nhận hàng'; validateReceive();}
      $$('[data-close-dialog]', dialog).forEach(b => b.disabled = false);
    }
  });
  if (dialog.hasAttribute('data-initial-open')) {dialog.showModal(); validateReceive();}
})();
