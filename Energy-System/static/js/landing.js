document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather icons
    feather.replace();
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#' || targetId === '#signup') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Handle tab selection for login/signup if coming from anchor link
    if (window.location.hash === '#signup') {
        const signupTab = document.querySelector('a[data-bs-toggle="tab"][href="#signup"]');
        if (signupTab) {
            const tab = new bootstrap.Tab(signupTab);
            tab.show();
        }
    }
    
    // Add animation on scroll for features and benefits sections
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.feature-card, .testimonial-card, .dashboard-img-container');
        
        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const windowHeight = window.innerHeight;
            
            if (elementPosition < windowHeight - 100) {
                if (!element.classList.contains('animate__animated')) {
                    element.classList.add('animate__animated', 'animate__fadeInUp');
                }
            }
        });
    };
    
    // Add animation class on page load
    setTimeout(animateOnScroll, 300);
    
    // Add animation class on scroll
    window.addEventListener('scroll', animateOnScroll);
});