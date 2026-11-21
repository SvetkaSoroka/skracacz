// Home page: send the long link to the API and show the result.

const form = document.getElementById('form');
const input = document.getElementById('url');
const help = document.getElementById('help');
const button = form.querySelector('button');
const result = document.getElementById('result');

function showError(message) {
  input.setAttribute('aria-invalid', 'true');
  help.textContent = message;
  help.classList.add('is-error');
  input.focus();
}

function clearError() {
  input.removeAttribute('aria-invalid');
  help.textContent = 'No account needed.';
  help.classList.remove('is-error');
}

async function copy(text, btn) {
  await navigator.clipboard.writeText(text);
  btn.textContent = 'Copied';
  setTimeout(() => { btn.textContent = 'Copy'; }, 1800);
}

input.addEventListener('input', clearError);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const url = input.value.trim();
  if (!url) {
    showError('Paste a link to shorten.');
    return;
  }

  button.disabled = true;
  button.textContent = 'Shortening';
  try {
    const response = await fetch('/api/links', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error);
      return;
    }

    clearError();
    const shortLink = document.getElementById('short-link');
    shortLink.textContent = data.short_url.replace(/^https?:\/\//, '');
    shortLink.href = data.short_url;
    document.getElementById('stats-link').textContent = data.stats_url;
    document.getElementById('open-stats').href = data.stats_url;
    document.getElementById('copy-short').onclick = (e) => copy(data.short_url, e.target);
    document.getElementById('copy-stats').onclick = (e) => copy(data.stats_url, e.target);

    form.hidden = true;
    result.hidden = false;
    document.getElementById('copy-short').focus();
  } catch {
    showError('No connection to the server. Check your internet and try again.');
  } finally {
    button.disabled = false;
    button.textContent = 'Shorten';
  }
});

document.getElementById('again').addEventListener('click', () => {
  result.hidden = true;
  form.hidden = false;
  input.value = '';
  clearError();
  input.focus();
});
