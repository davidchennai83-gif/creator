import { Component, ErrorInfo, ReactNode } from 'react';

export default class AppErrorBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Application render failed', error, info.componentStack); }
  render() {
    if (this.state.failed) return <section className="p-8 space-y-4" role="alert">
      <h1 className="text-2xl font-bold">The application could not display this page</h1>
      <p>Please reload. If the problem continues, share a screenshot of this message.</p>
      <button className="bg-teal-700 text-white p-3 rounded" onClick={()=>window.location.reload()}>Reload application</button>
    </section>;
    return this.props.children;
  }
}
