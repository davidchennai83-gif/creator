import { useEffect, useId, useRef, ReactNode } from 'react';
export function Modal({isOpen,onClose,title,children}:{isOpen:boolean;onClose:()=>void;title:string;children:ReactNode}){
  const ref=useRef<HTMLDialogElement>(null);const id=useId();
  useEffect(()=>{const dialog=ref.current;if(isOpen && !dialog?.open)dialog?.showModal();if(!isOpen && dialog?.open)dialog?.close();},[isOpen]);
  return <dialog ref={ref} aria-labelledby={id} onCancel={e=>{e.preventDefault();onClose();}} className="rounded-xl p-6 max-w-lg w-full backdrop:bg-black/50"><div className="flex justify-between gap-4"><h2 id={id} className="font-bold text-lg">{title}</h2><button type="button" aria-label="Close dialog" onClick={onClose}>✕</button></div>{isOpen && children}</dialog>;
}
