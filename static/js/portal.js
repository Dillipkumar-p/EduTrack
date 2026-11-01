// EduTrack Portal JavaScript Helpers

document.addEventListener('DOMContentLoaded', () => {
  // Live marks calculator in Marks Entry form
  const examSelect = document.getElementById('exam_id');
  const marksInput = document.getElementById('marks_obtained');
  const previewBox = document.getElementById('marks-preview');

  function updateMarksPreview() {
    if (!examSelect || !marksInput || !previewBox) return;

    const selectedOption = examSelect.options[examSelect.selectedIndex];
    if (!selectedOption || !selectedOption.dataset.max) {
      previewBox.innerHTML = '';
      return;
    }

    const max = parseFloat(selectedOption.dataset.max);
    const pass = parseFloat(selectedOption.dataset.pass);
    const entered = parseFloat(marksInput.value);

    if (isNaN(entered)) {
      previewBox.innerHTML = `<span class="form-hint">Max for this exam: ${max} | Pass: ${pass}</span>`;
      return;
    }

    if (entered < 0 || entered > max) {
      previewBox.innerHTML = `<span class="badge badge-danger">Out of bounds! Maximum is ${max}</span>`;
      return;
    }

    const pct = ((entered / max) * 100).toFixed(1);
    const isPassed = entered >= pass;
    const badgeClass = isPassed ? 'badge-lime' : 'badge-danger';
    const statusText = isPassed ? 'PASSED' : 'NEEDS ASSISTANCE / FAIL';

    previewBox.innerHTML = `
      <span class="badge ${badgeClass}">${pct}% (${statusText})</span>
      <span class="form-hint" style="margin-left: 8px;">Passing requirement: ${pass}/${max}</span>
    `;
  }

  if (examSelect && marksInput) {
    examSelect.addEventListener('change', updateMarksPreview);
    marksInput.addEventListener('input', updateMarksPreview);
    updateMarksPreview();
  }
});
