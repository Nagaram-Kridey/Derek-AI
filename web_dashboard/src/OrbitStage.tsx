import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import './orbit-stage.css';

/** Decorative introduction only: never represents live tasks or service state. */
export function OrbitStage() {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add('(prefers-reduced-motion: no-preference)', () => {
      if (!root.current) return;
      const node = root.current;
      const plane = node.querySelector('.orbit-plane');
      // Pointer-driven depth only: no continuous motion requiring a pause control.
      const xTo = gsap.quickTo(plane, 'rotationX', { duration: .7 });
      const yTo = gsap.quickTo(plane, 'rotationY', { duration: .7 });
      const move = (event: PointerEvent) => {
        if (event.pointerType !== 'mouse') return;
        const rect = node.getBoundingClientRect();
        xTo(10 - (event.clientY - rect.top) / rect.height * 8);
        yTo(-12 + (event.clientX - rect.left) / rect.width * 12);
      };
      const reset = () => { xTo(6); yTo(-6); };
      node.addEventListener('pointermove', move);
      node.addEventListener('pointerleave', reset);
      return () => {
        node.removeEventListener('pointermove', move);
        node.removeEventListener('pointerleave', reset);
        gsap.killTweensOf(plane);
        gsap.set(plane, { clearProps: 'transform' });
      };
    });
    return () => media.revert();
  }, []);
  return <div className="orbit-welcome">
    <span className="eyebrow">YOUR PERSONAL SPACE FOR POSSIBILITY</span>
    <h2 className="orbit-heading">Less on your mind.<br /><span>More in your world.</span></h2>
    <div className="orbit-stage" ref={root}>
      <div className="orbit-halo" aria-hidden="true" />
      <div className="orbit-plane" aria-hidden="true">
        <div className="orbit-mini-board"><b>derek.</b><span>A LITTLE ROOM TO THINK</span><strong>Good things start small.</strong><div className="orbit-mini-input">A rough thought is enough. <span>↗</span></div><div className="orbit-mini-tiles"><span>Find the thread.<i>From an idea to a next step.</i></span><span>Make some space.<i>Go at your own pace.</i></span></div></div>
        <span className="orbit-float orbit-float-one">✦ A thought. A possibility.</span>
        <span className="orbit-float orbit-float-two">Your next chapter starts here.</span>
      </div>
    </div>
  </div>;
}
