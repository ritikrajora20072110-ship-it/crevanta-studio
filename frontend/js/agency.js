/**
 * CREVANTA — LUXURY EDITORIAL AGENCY INTERACTIVE CONTROLLER
 * "Where brands meet influence. Creators × Advantage."
 */

document.addEventListener('DOMContentLoaded', () => {
  initCustomCursor();
  initStickyNav();
  initScrollReveals();
  initCreatorFilters();
  initCampaignTimeline();
  initModalsAndDrawers();
  initForms();
  initCategoryHover();
});

/* ==========================================================================
   1. CUSTOM DESKTOP CURSOR (VIEW → Badge)
   ========================================================================== */
function initCustomCursor() {
  const dot = document.querySelector('.cursor-dot');
  const circle = document.querySelector('.cursor-circle');

  if (!dot || !circle || window.matchMedia('(pointer: coarse)').matches) return;

  let mouseX = 0, mouseY = 0;
  let circleX = 0, circleY = 0;

  window.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    dot.style.left = `${mouseX}px`;
    dot.style.top = `${mouseY}px`;
  });

  function animateCursor() {
    circleX += (mouseX - circleX) * 0.15;
    circleY += (mouseY - circleY) * 0.15;
    circle.style.left = `${circleX}px`;
    circle.style.top = `${circleY}px`;
    requestAnimationFrame(animateCursor);
  }
  animateCursor();

  // Attach hover triggers
  const viewTriggers = document.querySelectorAll('[data-cursor="view"]');
  viewTriggers.forEach(el => {
    el.addEventListener('mouseenter', () => {
      circle.classList.add('view-mode');
      circle.innerText = 'VIEW →';
      dot.style.opacity = '0';
    });
    el.addEventListener('mouseleave', () => {
      circle.classList.remove('view-mode');
      circle.innerText = '';
      dot.style.opacity = '1';
    });
  });
}

/* ==========================================================================
   2. STICKY NAVBAR SCROLL TRANSITION
   ========================================================================== */
function initStickyNav() {
  const navbar = document.querySelector('.editorial-navbar');
  if (!navbar) return;

  window.addEventListener('scroll', () => {
    if (window.scrollY > 40) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }, { passive: true });
}

/* ==========================================================================
   3. SCROLL REVEALS
   ========================================================================== */
function initScrollReveals() {
  const elements = document.querySelectorAll('.reveal-on-scroll');
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  elements.forEach(el => observer.observe(el));
}

/* ==========================================================================
   4. CREATOR SHOWCASE FILTERS
   ========================================================================== */
function initCreatorFilters() {
  const filterTabs = document.querySelectorAll('.filter-tab');
  const creatorCards = document.querySelectorAll('.creator-grid-item');

  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const filter = tab.getAttribute('data-filter');

      creatorCards.forEach(card => {
        const category = card.getAttribute('data-category');
        if (filter === 'all' || category === filter) {
          card.style.display = 'block';
          setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
          }, 50);
        } else {
          card.style.opacity = '0';
          card.style.transform = 'translateY(12px)';
          setTimeout(() => {
            card.style.display = 'none';
          }, 250);
        }
      });
    });
  });
}

/* ==========================================================================
   5. 15-DAY CAMPAIGN INTERACTIVE TIMELINE
   ========================================================================== */
const TIMELINE_DATA = {
  1: {
    day: "DAY 01",
    phase: "Campaign Kickoff & Creative Brief",
    deliverables: "Strategic Alignment · Creator Onboarding",
    description: "Crevanta finalizes campaign objectives, product sample deliveries, creative narrative arcs, and strict compliance guidelines with selected creators."
  },
  3: {
    day: "DAY 03–05",
    phase: "Hero Content Production & Review",
    deliverables: "60s Editorial Reels · 4K B-Roll Visuals",
    description: "Creators produce authentic, high-retention content naturally integrating the brand into their daily rituals. Crevanta reviews drafts before release."
  },
  7: {
    day: "DAY 07",
    phase: "Audience Engagement & Community Dialogue",
    deliverables: "Interactive Story Sequences · Swipe-ups / Bio Links",
    description: "Creators initiate authentic community conversations, answer product questions via Instagram Stories, and direct high-intent followers to brand links."
  },
  10: {
    day: "DAY 10",
    phase: "Content Amplification & Retargeting",
    deliverables: "Collaborative Co-Author Posts · Second Hook Variation",
    description: "Crevanta facilitates Instagram Collab posts appearing on both the brand and creator's profile feeds, doubling organic reach and social validation."
  },
  15: {
    day: "DAY 15",
    phase: "Wrap-up, Analytics & Asset Handover",
    deliverables: "Verified Performance Report · Content Licensing",
    description: "Complete performance report including verified reach, impressions, engagement rates, click-throughs, and rights handover for brand ad amplification."
  }
};

function initCampaignTimeline() {
  const milestones = document.querySelectorAll('.timeline-milestone');
  const displayDay = document.getElementById('timelineDetailDay');
  const displayPhase = document.getElementById('timelineDetailPhase');
  const displayDeliverables = document.getElementById('timelineDetailDeliverables');
  const displayDesc = document.getElementById('timelineDetailDesc');

  if (!milestones.length || !displayDay) return;

  milestones.forEach(m => {
    m.addEventListener('click', () => {
      milestones.forEach(item => item.classList.remove('active'));
      m.classList.add('active');

      const step = m.getAttribute('data-step');
      const data = TIMELINE_DATA[step];

      if (data) {
        displayDay.innerText = data.day;
        displayPhase.innerText = data.phase;
        displayDeliverables.innerText = data.deliverables;
        displayDesc.innerText = data.description;
      }
    });
  });
}

/* ==========================================================================
   6. MODALS & DRAWERS (Creator Detail, Enquiries, Applications)
   ========================================================================== */
function initModalsAndDrawers() {
  // Mobile Menu Toggle
  const mobileToggle = document.getElementById('mobileMenuToggle');
  const mobileMenu = document.getElementById('mobileMenuOverlay');
  const mobileClose = document.getElementById('mobileMenuClose');
  const mobileLinks = document.querySelectorAll('.mobile-nav-item');

  if (mobileToggle && mobileMenu) {
    mobileToggle.addEventListener('click', () => mobileMenu.classList.add('open'));
    if (mobileClose) mobileClose.addEventListener('click', () => mobileMenu.classList.remove('open'));
    mobileLinks.forEach(link => {
      link.addEventListener('click', () => mobileMenu.classList.remove('open'));
    });
  }

  // Creator Slide-over Drawer
  const creatorBackdrop = document.getElementById('creatorDrawerBackdrop');
  const creatorDrawer = document.getElementById('creatorDrawer');
  const creatorClose = document.getElementById('creatorDrawerClose');

  if (creatorClose && creatorBackdrop && creatorDrawer) {
    creatorClose.addEventListener('click', closeCreatorDrawer);
    creatorBackdrop.addEventListener('click', (e) => {
      if (e.target === creatorBackdrop) closeCreatorDrawer();
    });
  }

  // Brand Campaign Enquiry Modal
  const enquiryModal = document.getElementById('enquiryModal');
  const openEnquiryBtns = document.querySelectorAll('[data-open-enquiry]');
  const closeEnquiryBtn = document.getElementById('enquiryModalClose');

  openEnquiryBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (enquiryModal) enquiryModal.classList.remove('hidden');
    });
  });

  if (closeEnquiryBtn && enquiryModal) {
    closeEnquiryBtn.addEventListener('click', () => enquiryModal.classList.add('hidden'));
    enquiryModal.addEventListener('click', (e) => {
      if (e.target === enquiryModal) enquiryModal.classList.add('hidden');
    });
  }

  // Creator Join Application Modal
  const joinModal = document.getElementById('joinModal');
  const openJoinBtns = document.querySelectorAll('[data-open-join]');
  const closeJoinBtn = document.getElementById('joinModalClose');

  openJoinBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (joinModal) joinModal.classList.remove('hidden');
    });
  });

  if (closeJoinBtn && joinModal) {
    closeJoinBtn.addEventListener('click', () => joinModal.classList.add('hidden'));
    joinModal.addEventListener('click', (e) => {
      if (e.target === joinModal) joinModal.classList.add('hidden');
    });
  }
}

function openCreatorDrawer(creatorData) {
  const backdrop = document.getElementById('creatorDrawerBackdrop');
  const drawer = document.getElementById('creatorDrawer');
  if (!backdrop || !drawer) return;

  document.getElementById('drawerCreatorName').innerText = creatorData.name || '';
  document.getElementById('drawerCreatorHandle').innerText = creatorData.handle || '';
  document.getElementById('drawerCreatorNiche').innerText = creatorData.niche || '';
  document.getElementById('drawerCreatorLocation').innerText = creatorData.location || '';
  document.getElementById('drawerCreatorFollowers').innerText = creatorData.followers || '';
  document.getElementById('drawerCreatorEngagement').innerText = creatorData.engagement_rate || '';
  document.getElementById('drawerCreatorViews').innerText = creatorData.avg_views || '';
  document.getElementById('drawerCreatorBio').innerText = creatorData.bio || '';
  document.getElementById('drawerCreatorImage').src = creatorData.image || creatorData.editorial_image || '';

  // Demographics
  if (creatorData.audience) {
    document.getElementById('drawerDemographics').innerText = creatorData.audience.demographics || 'Broad';
    document.getElementById('drawerAge').innerText = creatorData.audience.age || '20-35';
    document.getElementById('drawerLocations').innerText = creatorData.audience.locations || 'Global Tier-1';
  }

  // Content Pillars
  const pillarsList = document.getElementById('drawerPillarsList');
  if (pillarsList && creatorData.content_pillars) {
    pillarsList.innerHTML = creatorData.content_pillars.map(p => `<li class="py-1 border-b border-[#D9D6CE]/60 flex items-center gap-2"><span class="text-[#A68A5B]">✦</span> ${p}</li>`).join('');
  }

  // Past Brands
  const pastBrandsElem = document.getElementById('drawerPastBrands');
  if (pastBrandsElem && creatorData.past_brands) {
    pastBrandsElem.innerText = creatorData.past_brands.join(' · ');
  }

  // Pre-fill CTA button
  const ctaBtn = document.getElementById('drawerWorkWithBtn');
  if (ctaBtn) {
    ctaBtn.onclick = () => {
      closeCreatorDrawer();
      const enquiryModal = document.getElementById('enquiryModal');
      const notesField = document.getElementById('enquiryMessage');
      if (notesField) {
        notesField.value = `Interested in working with ${creatorData.name} (${creatorData.handle}).`;
      }
      if (enquiryModal) enquiryModal.classList.remove('hidden');
    };
  }

  backdrop.classList.add('open');
  drawer.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeCreatorDrawer() {
  const backdrop = document.getElementById('creatorDrawerBackdrop');
  const drawer = document.getElementById('creatorDrawer');
  if (backdrop && drawer) {
    backdrop.classList.remove('open');
    drawer.classList.remove('open');
    document.body.style.overflow = '';
  }
}

/* ==========================================================================
   7. BRAND CATEGORIES HOVER IMAGES
   ========================================================================== */
function initCategoryHover() {
  const rows = document.querySelectorAll('.category-row');
  rows.forEach(row => {
    const preview = row.querySelector('.category-preview-img');
    if (!preview) return;

    row.addEventListener('mousemove', (e) => {
      const rect = row.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      preview.style.left = `${relX + 40}px`;
    });
  });
}

/* ==========================================================================
   8. FORM SUBMISSIONS (Brand Enquiry & Creator Join)
   ========================================================================== */
function initForms() {
  // Brand Campaign Enquiry Form
  const enquiryForm = document.getElementById('brandEnquiryForm');
  if (enquiryForm) {
    enquiryForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = enquiryForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;

      const payload = {
        brand_name: document.getElementById('enquiryBrandName').value.trim(),
        website: document.getElementById('enquiryWebsite').value.trim(),
        contact_name: document.getElementById('enquiryContactName').value.trim(),
        email: document.getElementById('enquiryEmail').value.trim(),
        campaign_objective: document.getElementById('enquiryObjective').value.trim(),
        budget_range: document.getElementById('enquiryBudget').value,
        message: document.getElementById('enquiryMessage').value.trim()
      };

      if (!payload.brand_name || !payload.email) {
        alert('Please provide your brand name and email address.');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerText = 'TRANSMITTING REQUEST...';

      try {
        const res = await fetch('/api/inquiries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          enquiryForm.innerHTML = `
            <div class="py-12 text-center space-y-4">
              <span class="text-xs uppercase tracking-widest text-[#A68A5B] font-semibold">REQUEST RECEIVED</span>
              <h3 class="font-serif text-3xl text-[#171717]">Thank you. We'll be in touch shortly.</h3>
              <p class="text-sm text-[#696963] max-w-md mx-auto">
                A Crevanta partnership director will review your campaign brief and present curated creator options within 24 hours.
              </p>
            </div>
          `;
        } else {
          throw new Error('Server returned an error');
        }
      } catch (err) {
        alert('Failed to send enquiry. Please try again or email us directly.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }

  // Creator Join Application Form
  const joinForm = document.getElementById('creatorJoinForm');
  if (joinForm) {
    joinForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = joinForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;

      const payload = {
        name: document.getElementById('joinName').value.trim(),
        handle: document.getElementById('joinHandle').value.trim(),
        youtube: document.getElementById('joinYoutube').value.trim(),
        niche: document.getElementById('joinNiche').value.trim(),
        followers: document.getElementById('joinFollowers').value.trim(),
        email: document.getElementById('joinEmail').value.trim(),
        location: document.getElementById('joinLocation').value.trim(),
        past_collabs: document.getElementById('joinCollabs').value.trim()
      };

      if (!payload.name || !payload.handle || !payload.email) {
        alert('Please complete all required fields.');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerText = 'TRANSMITTING APPLICATION...';

      try {
        const res = await fetch('/api/creator-applications', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          joinForm.innerHTML = `
            <div class="py-12 text-center space-y-4">
              <span class="text-xs uppercase tracking-widest text-[#A68A5B] font-semibold">APPLICATION RECEIVED</span>
              <h3 class="font-serif text-3xl text-[#171717]">Welcome to Crevanta.</h3>
              <p class="text-sm text-[#696963] max-w-md mx-auto">
                Our talent team carefully curates our creator roster. We review profiles weekly and will contact you if your audience aligns with our upcoming brand campaigns.
              </p>
            </div>
          `;
        } else {
          throw new Error('Server returned an error');
        }
      } catch (err) {
        alert('Failed to submit application. Please try again.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }
}
