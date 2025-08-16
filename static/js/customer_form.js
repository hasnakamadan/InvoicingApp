document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form');
  const company = document.getElementById('company_name');
  const email = document.getElementById('email');
  const postal = document.getElementById('postal_code');
  const country = document.getElementById('country');

  function showError(input, message) {
    const error = document.querySelector(`[data-error-for="${input.name}"]`);
    if (error) {
      error.textContent = message;
      error.classList.remove('hidden');
    }
    input.classList.add('border-rose-400');
  }

  function clearError(input) {
    const error = document.querySelector(`[data-error-for="${input.name}"]`);
    if (error) {
      error.textContent = '';
      error.classList.add('hidden');
    }
    input.classList.remove('border-rose-400');
  }

  function validateField(input) {
    if (input.name === 'company_name') {
      if (!input.value.trim()) {
        showError(input, 'Company name is required');
        return false;
      }
      clearError(input);
      return true;
    }
    if (input.name === 'email') {
      const value = input.value.trim();
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!value || !emailRegex.test(value)) {
        showError(input, 'Enter a valid email');
        return false;
      }
      clearError(input);
      return true;
    }
    return true;
  }

  function formatPostalByCountry() {
    const c = country.value;
    let v = postal.value.trim();
    if (c === 'United States') {
      const digits = v.replace(/\D/g, '');
      if (digits.length === 5) {
        v = digits;
      } else if (digits.length === 9) {
        v = digits.slice(0,5) + '-' + digits.slice(5);
      }
      postal.value = v;
    } else if (c === 'United Kingdom') {
      const noSpace = v.replace(/\s+/g, '');
      const ukRegex = /^[A-Za-z]{1,2}\d[A-Za-z\d]?\d[A-Za-z]{2}$/;
      if (ukRegex.test(noSpace)) {
        postal.value = noSpace.slice(0, noSpace.length - 3) + ' ' + noSpace.slice(-3);
      }
    } else if (c === 'Canada') {
      const noSpace = v.replace(/\s+/g, '').toUpperCase();
      const caRegex = /^[A-Z]\d[A-Z]\d[A-Z]\d$/;
      if (caRegex.test(noSpace)) {
        postal.value = noSpace.slice(0,3) + ' ' + noSpace.slice(3);
      }
    }
  }

  function updatePostalHint() {
    const hint = document.getElementById('postal_hint');
    if (!hint) return;
    let text = '';
    switch(country.value) {
      case 'United States':
        text = 'Format: 12345 or 12345-6789';
        break;
      case 'United Kingdom':
        text = 'Format: SW1A 1AA';
        break;
      case 'Canada':
        text = 'Format: A1A 1A1';
        break;
      default:
        text = '';
    }
    hint.textContent = text;
  }

  company.addEventListener('blur', () => validateField(company));
  email.addEventListener('blur', () => validateField(email));
  postal.addEventListener('blur', () => formatPostalByCountry());
  country.addEventListener('change', () => updatePostalHint());

  updatePostalHint();

  form.addEventListener('submit', (e) => {
    const okCompany = validateField(company);
    const okEmail = validateField(email);
    formatPostalByCountry();
    if (!okCompany || !okEmail) {
      e.preventDefault();
    }
  });
});
