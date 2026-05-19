const signal = { dispatch: null };

export function toast(message, type = 'success') {
  signal.dispatch?.({ message, type, id: Date.now() + Math.random() });
}
toast.success = (msg) => toast(msg, 'success');
toast.error   = (msg) => toast(msg, 'error');
toast.warn    = (msg) => toast(msg, 'warn');

export { signal as toastSignal };
