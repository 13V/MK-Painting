/* Smooth scroll for anchor links */
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

/* Telegram instant notification */
function sendTelegramNotification(formData) {
    const BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE';
    const CHAT_ID = 'YOUR_CHAT_ID_HERE';
    const text = `🎨 New Lead!\n\nName: ${formData.name || 'N/A'}\nPhone: ${formData.phone || 'N/A'}\nSuburb: ${formData.suburb || 'N/A'}\nService: ${formData.service || 'N/A'}\nMessage: ${formData.message || '—'}\n\nFrom: ${formData.subject || 'Website'}`;
    fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: CHAT_ID, text: text, parse_mode: 'HTML' })
    }).catch(err => console.log('Telegram notification failed:', err));
}

/* Form submission — AJAX via Web3Forms */
const quoteForms = document.querySelectorAll('#quoteForm, #heroQuoteForm, #contactPageForm');
quoteForms.forEach(form => {
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const formData = new FormData(form);
        const object = Object.fromEntries(formData);
        const json = JSON.stringify(object);
        const submitBtn = form.querySelector('.btn-submit');
        const originalBtnText = submitBtn.textContent;
        submitBtn.textContent = 'Sending...';
        submitBtn.disabled = true;

        fetch('https://api.web3forms.com/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: json
        })
        .then(async (response) => {
            let json = await response.json();
            if (response.status == 200) {
                sendTelegramNotification(object);
                form.reset();
                window.location.href = '/thank-you.html';
            } else {
                console.log(response);
                showFormMessage(form, 'error', "Something went wrong. Please call us directly.");
            }
        })
        .catch(error => {
            console.log(error);
            showFormMessage(form, 'error', "Connection error. Please try again.");
        })
        .then(function () {
            submitBtn.textContent = originalBtnText;
            submitBtn.disabled = false;
        });
    });
});

function showFormMessage(form, type, message) {
    const existing = form.querySelector('.form-message');
    if (existing) existing.remove();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'form-message ' + type;
    msgDiv.innerHTML = type === 'success'
        ? '<span class="msg-icon">\u2713</span> ' + message
        : '<span class="msg-icon">\u2715</span> ' + message;
    const submitBtn = form.querySelector('.btn-submit');
    submitBtn.insertAdjacentElement('afterend', msgDiv);
    setTimeout(() => {
        msgDiv.style.opacity = '0';
        setTimeout(() => msgDiv.remove(), 300);
    }, 5000);
}

/* Navbar scroll shadow */
const navbar = document.querySelector('.navbar');
if (navbar) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
        } else {
            navbar.style.boxShadow = 'none';
        }
    });
}

/* Quote calculator (only runs on pages with the calculator elements) */
const projectType = document.getElementById('projectType');
const roomCount = document.getElementById('roomCount');
const roomSize = document.getElementById('roomSize');
const ceiling = document.getElementById('ceiling');
const calcResult = document.getElementById('calcResult');

if (projectType && roomCount && roomSize && ceiling && calcResult) {
    const basePrices = {
        interior: { small: 350, medium: 500, large: 700 },
        exterior: { small: 800, medium: 1200, large: 1800 },
        full: { small: 1500, medium: 2200, large: 3200 }
    };

    function calculateQuote() {
        const type = projectType.value;
        const rooms = parseInt(roomCount.value);
        const size = roomSize.value;
        const hasCeiling = ceiling.value === 'yes';
        let basePrice = basePrices[type][size];
        let total = basePrice * rooms;
        if (hasCeiling) { total = total * 1.3; }
        const low = Math.round(total * 0.85);
        const high = Math.round(total * 1.15);
        calcResult.textContent = '$' + low.toLocaleString() + ' - $' + high.toLocaleString();
    }

    [projectType, roomCount, roomSize, ceiling].forEach(input => {
        input.addEventListener('change', calculateQuote);
    });
    calculateQuote();
}

/* Gallery lightbox */
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightbox-img');
const lightboxClose = document.querySelector('.lightbox-close');
const galleryItems = document.querySelectorAll('.gallery-item img');

if (lightbox && lightboxImg && galleryItems.length > 0) {
    galleryItems.forEach(img => {
        img.parentElement.addEventListener('click', () => {
            lightboxImg.src = img.src;
            lightbox.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        });
    });

    const closeLightbox = () => {
        lightbox.style.display = 'none';
        document.body.style.overflow = 'auto';
    };

    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeLightbox);
    }
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) { closeLightbox(); }
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.style.display === 'flex') { closeLightbox(); }
    });
}

/* FAQ accordion */
const faqItems = document.querySelectorAll('.faq-item');
faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    if (question) {
        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            faqItems.forEach(otherItem => { otherItem.classList.remove('active'); });
            if (!isActive) { item.classList.add('active'); }
        });
    }
});

/* Phone call click tracking — GA4 */
document.querySelectorAll('a[href^="tel:"]').forEach(function (link) {
    link.addEventListener('click', function () {
        if (typeof gtag === 'function') {
            gtag('event', 'phone_call_click', {
                event_category: 'contact',
                event_label: link.href.replace('tel:', '')
            });
        }
    });
});
