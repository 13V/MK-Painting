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

// Form
const form = document.getElementById('quoteForm');
form.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = data.get('name');
    const phone = data.get('phone');
    alert(`Thanks ${name}! We'll call you at ${phone} within 24 hours.`);
    form.reset();
});

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

// Gallery Carousel
const track = document.getElementById('carouselTrack');
const slides = document.querySelectorAll('.carousel-slide');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const dotsContainer = document.getElementById('carouselDots');

let currentIndex = 0;
const totalSlides = slides.length;

// Create dots
slides.forEach((_, index) => {
    const dot = document.createElement('button');
    dot.classList.add('carousel-dot');
    if (index === 0) dot.classList.add('active');
    dot.addEventListener('click', () => goToSlide(index));
    dotsContainer.appendChild(dot);
});

const dots = document.querySelectorAll('.carousel-dot');

function updateCarousel() {
    track.style.transform = `translateX(-${currentIndex * 100}%)`;
    dots.forEach((dot, index) => {
        dot.classList.toggle('active', index === currentIndex);
    });
}

function goToSlide(index) {
    currentIndex = index;
    updateCarousel();
}

function nextSlide() {
    currentIndex = (currentIndex + 1) % totalSlides;
    updateCarousel();
}

function prevSlide() {
    currentIndex = (currentIndex - 1 + totalSlides) % totalSlides;
    updateCarousel();
}

prevBtn.addEventListener('click', prevSlide);
nextBtn.addEventListener('click', nextSlide);

// Auto-advance every 5 seconds
setInterval(nextSlide, 5000);
