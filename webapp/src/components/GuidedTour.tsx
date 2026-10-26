import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, ChevronRight, ChevronLeft } from 'lucide-react';

const TOUR_STEPS = [
  {
    title: "Welcome to Project IKNOS",
    content: "This is the Settlement Officer HQ. From here, you can orchestrate the entire 3-layer boundary fusion process.",
    target: "center",
    action: null
  },
  {
    title: "Layer 1 & 2: The Queue",
    content: "Click 'Case Queue' to see all pending land parcels. This combines Cadastral (Layer 1) with AI Satellite inference (Layer 2) to flag spatial discrepancies automatically.",
    target: "nav-cases",
    action: "/admin/cases"
  },
  {
    title: "Honest AI Evaluation",
    content: "We don't hide our AI metrics. Check 'AI Evaluation' to see the exact confusion matrix, F1 scores, and IoU for our U-Net model.",
    target: "nav-evaluation",
    action: "/admin/evaluation"
  },
  {
    title: "Layer 3: Drone Truth",
    content: "If the AI and Cadastral layers clash, we send a Surveyor. The Surveyor uses the mobile app to fly a drone, run offline AI, and submit the final ground truth (Layer 3).",
    target: "center",
    action: null
  }
];

export const GuidedTour: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('iknos_tour_completed');
    if (!hasSeenTour) {
      setIsOpen(true);
    }
  }, []);

  const handleClose = () => {
    localStorage.setItem('iknos_tour_completed', 'true');
    setIsOpen(false);
  };

  const handleNext = () => {
    if (currentStep < TOUR_STEPS.length - 1) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      const action = TOUR_STEPS[nextStep].action;
      if (action) {
        navigate(action);
      }
    } else {
      handleClose();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      const prevStep = currentStep - 1;
      setCurrentStep(prevStep);
      const action = TOUR_STEPS[prevStep].action;
      if (action) {
        navigate(action);
      }
    }
  };

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      pointerEvents: 'none',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      {/* Dark overlay */}
      <div 
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', pointerEvents: 'auto' }}
        onClick={handleClose}
      />
      
      {/* Tour Modal */}
      <div style={{
        position: 'relative',
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '24px',
        width: '400px',
        maxWidth: '90%',
        boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
        pointerEvents: 'auto',
        transform: step.target === 'center' ? 'none' : 'translate(100px, -50px)',
        transition: 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)'
      }}>
        {/* Close Button */}
        <button 
          onClick={handleClose}
          style={{ position: 'absolute', top: 12, right: 12, background: 'transparent', border: 'none', color: 'var(--text-2)', cursor: 'pointer' }}
        >
          <X size={18} />
        </button>

        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
          TOUR • {currentStep + 1} / {TOUR_STEPS.length}
        </div>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '18px', color: 'var(--text-1)' }}>
          {step.title}
        </h3>
        <p style={{ margin: '0 0 24px 0', fontSize: '14px', color: 'var(--text-2)', lineHeight: 1.5 }}>
          {step.content}
        </p>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button 
            onClick={handleClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-3)', fontSize: '12px', cursor: 'pointer', fontWeight: 600 }}
          >
            SKIP TOUR
          </button>
          <div style={{ display: 'flex', gap: '8px' }}>
            {currentStep > 0 && (
              <button onClick={handlePrev} className="btn btn-outline" style={{ padding: '6px 10px' }}>
                <ChevronLeft size={16} />
              </button>
            )}
            <button onClick={handleNext} className="btn btn-primary" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {currentStep === TOUR_STEPS.length - 1 ? 'FINISH' : 'NEXT'} <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
