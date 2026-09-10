// Confetti animation for celebrations
// Usage: window.launchConfetti()

(function() {
  const canvas = document.getElementById('confetti-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];
  let animating = false;
  
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();
  
  const COLORS = ['#22c55e', '#3b82f6', '#f97316', '#ec4899', '#a855f7', '#eab308', '#06b6d4'];
  
  class Particle {
    constructor() {
      this.x = canvas.width / 2;
      this.y = canvas.height / 2;
      this.vx = (Math.random() - 0.5) * 20;
      this.vy = (Math.random() - 1) * 20;
      this.color = COLORS[Math.floor(Math.random() * COLORS.length)];
      this.size = Math.random() * 8 + 4;
      this.rotation = Math.random() * 360;
      this.rotationSpeed = (Math.random() - 0.5) * 10;
      this.opacity = 1;
      this.gravity = 0.3;
      this.drag = 0.98;
      this.shape = Math.random() > 0.5 ? 'rect' : 'circle'; // mix of shapes
    }
    
    update() {
      this.vy += this.gravity;
      this.vx *= this.drag;
      this.vy *= this.drag;
      this.x += this.vx;
      this.y += this.vy;
      this.rotation += this.rotationSpeed;
      this.opacity -= 0.008;
    }
    
    draw() {
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate((this.rotation * Math.PI) / 180);
      ctx.globalAlpha = Math.max(0, this.opacity);
      ctx.fillStyle = this.color;
      if (this.shape === 'rect') {
        ctx.fillRect(-this.size / 2, -this.size / 4, this.size, this.size / 2);
      } else {
        ctx.beginPath();
        ctx.arc(0, 0, this.size / 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }
  
  function animate() {
    if (!animating) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles = particles.filter(p => p.opacity > 0);
    particles.forEach(p => { p.update(); p.draw(); });
    if (particles.length > 0) {
      requestAnimationFrame(animate);
    } else {
      animating = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  
  window.launchConfetti = function(count = 150) {
    for (let i = 0; i < count; i++) {
      particles.push(new Particle());
    }
    if (!animating) {
      animating = true;
      animate();
    }
  };
})();
