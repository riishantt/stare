export function Loading({ text = "Loading..." }: { text?: string }) {
  return <p className="p-6 text-muted" role="status">{text}</p>;
}
export function ErrorBox({ message }: { message: string }) {
  return <div className="alert alert-bad" role="alert">{message}</div>;
}
