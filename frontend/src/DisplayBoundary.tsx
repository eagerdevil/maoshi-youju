import React from "react";
import { reportDisplayError, UI_BUILD } from "./displayErrors";

export default class DisplayBoundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportDisplayError("react", error, info.componentStack || "");
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="display-recovery" role="alert">
        <h1>分析页面遇到显示异常</h1>
        <p>错误已记录。已保存的分析和本地研究笔记草稿不会被清除。</p>
        <button
          className="button primary"
          onClick={() => window.location.reload()}
        >
          重新加载分析台
        </button>
        <small>
          界面版本 {UI_BUILD}。若再次出现，请保留此提示，便于继续定位。
        </small>
      </main>
    );
  }
}
