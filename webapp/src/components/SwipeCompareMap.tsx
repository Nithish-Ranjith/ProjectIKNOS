import React, { useState, useRef, useEffect } from 'react';
import { ArrowLeftRight, Layers } from 'lucide-react';

export const SwipeCompareMap: React.FC<{ beforeImg: string; afterImg: string; aiOverlay?: any }> = ({ beforeImg, afterImg, aiOverlay }) => {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleDrag = (e: React.MouseEvent | React.TouchEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    let clientX = 0;
    if ('touches' in e) {
      clientX = e.touches[0].clientX;
    } else {
      // @ts-ignore
      clientX = e.clientX;
    }
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const percent = (x / rect.width) * 100;
    setSliderPos(percent);
  };

  return (
    <div 
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: '500px', overflow: 'hidden', borderRadius: '12px', cursor: 'ew-resize', userSelect: 'none' }}
      onMouseMove={(e) => e.buttons === 1 && handleDrag(e)}
      onTouchMove={handleDrag}
    >
      {/* Historical Cadastral (Background - Right Side effectively) */}
      <div style={{ position: 'absolute', inset: 0, backgroundImage: `url(${beforeImg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}>
        <div style={{ position: 'absolute', top: 16, right: 16, background: 'rgba(0,0,0,0.7)', padding: '6px 12px', borderRadius: '8px', color: '#fff', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={14} color="var(--color-text-secondary)" /> 1950s Cadastral
        </div>
      </div>
      
      {/* Drone AI (Foreground Clipped - Left Side) */}
      <div style={{ 
        position: 'absolute', inset: 0, backgroundImage: `url(${afterImg})`, backgroundSize: 'cover', backgroundPosition: 'center',
        clipPath: `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)`
      }}>
        {aiOverlay && (
           <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
             {/* Just a stylized example representing the AI Boundary on top of the drone photo */}
             <polygon points="100,100 400,120 450,400 150,380" fill="rgba(46, 160, 67, 0.2)" stroke="var(--color-brand)" strokeWidth="3" strokeDasharray="5,5" />
           </svg>
        )}
        <div style={{ position: 'absolute', top: 16, left: 16, background: 'rgba(0,0,0,0.7)', padding: '6px 12px', borderRadius: '8px', color: '#fff', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={14} color="var(--color-brand)" /> Live AI Orthophoto
        </div>
      </div>
      
      {/* Draggable Divider */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${sliderPos}%`, width: '4px', background: '#fff',
        boxShadow: '0 0 10px rgba(0,0,0,0.8)', zIndex: 15, transform: 'translateX(-50%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        <div style={{ 
          width: '32px', height: '32px', background: '#fff', borderRadius: '50%', 
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#000',
          boxShadow: '0 2px 8px rgba(0,0,0,0.5)'
        }}>
          <ArrowLeftRight size={16} />
        </div>
      </div>
    </div>
  );
}
