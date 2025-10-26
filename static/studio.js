const form = document.getElementById('gen-form');
const result = document.getElementById('result');
const link = document.getElementById('site-link');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const payload = {
    title: fd.get('title')?.toString() ?? '',
    slug: fd.get('slug')?.toString() ?? '',
    prompt: fd.get('prompt')?.toString() ?? '',
  };

  form.querySelector('button[type="submit"]').disabled = true;

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error ?? 'Generation failed';
      alert(msg);
      return;
    }
    link.href = data.url;
    link.textContent = data.url;
    result.hidden = false;
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  } catch (err) {
    console.error(err);
    alert('Network error.');
  } finally {
    form.querySelector('button[type="submit"]').disabled = false;
  }
});

