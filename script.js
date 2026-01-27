// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Form handlers - AJAX submission for Web3Forms
const quoteForms = document.querySelectorAll('#quoteForm, #heroQuoteForm');
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
                    // Show success message
                    showFormMessage(form, 'success', "Quote Sent! We'll call you within 24 hours.");
                    form.reset();
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

// Show animated message on form
function showFormMessage(form, type, message) {
    // Remove any existing message
    const existing = form.querySelector('.form-message');
    if (existing) existing.remove();

    // Create message element
    const msgDiv = document.createElement('div');
    msgDiv.className = 'form-message ' + type;
    msgDiv.innerHTML = type === 'success'
        ? '<span class="msg-icon">✓</span> ' + message
        : '<span class="msg-icon">✕</span> ' + message;

    // Insert after submit button
    const submitBtn = form.querySelector('.btn-submit');
    submitBtn.insertAdjacentElement('afterend', msgDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        msgDiv.style.opacity = '0';
        setTimeout(() => msgDiv.remove(), 300);
    }, 5000);
}

// Navbar scroll effect
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
        navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
    } else {
        navbar.style.boxShadow = 'none';
    }
});

// Quote Calculator
const projectType = document.getElementById('projectType');
const roomCount = document.getElementById('roomCount');
const roomSize = document.getElementById('roomSize');
const ceiling = document.getElementById('ceiling');
const calcResult = document.getElementById('calcResult');

// Base prices
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

    // Get base price per room
    let basePrice = basePrices[type][size];

    // Multiply by rooms
    let total = basePrice * rooms;

    // Add ceiling (+30%)
    if (hasCeiling) {
        total = total * 1.3;
    }

    // Create range (±15%)
    const low = Math.round(total * 0.85);
    const high = Math.round(total * 1.15);

    // Format as currency
    calcResult.textContent = `$${low.toLocaleString()} - $${high.toLocaleString()}`;
}

// Add event listeners to all calculator inputs
[projectType, roomCount, roomSize, ceiling].forEach(input => {
    input.addEventListener('change', calculateQuote);
});

// Initial calculation
calculateQuote();

// Gallery Lightbox
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightbox-img');
const lightboxClose = document.querySelector('.lightbox-close');
const galleryItems = document.querySelectorAll('.gallery-item img');

if (lightbox && lightboxImg && galleryItems.length > 0) {
    galleryItems.forEach(img => {
        img.parentElement.addEventListener('click', () => {
            lightboxImg.src = img.src;
            lightbox.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // Prevent scroll
        });
    });

    const closeLightbox = () => {
        lightbox.style.display = 'none';
        document.body.style.overflow = 'auto';
    };

    lightboxClose.addEventListener('click', closeLightbox);

    // Close on click outside image
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.style.display === 'flex') {
            closeLightbox();
        }
    });
}

// FAQ Accordion
const faqItems = document.querySelectorAll('.faq-item');
faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
        const isActive = item.classList.contains('active');

        // Close all other items
        faqItems.forEach(otherItem => {
            otherItem.classList.remove('active');
        });

        // Toggle current item
        if (!isActive) {
            item.classList.add('active');
        }
    });
});
