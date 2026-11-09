import OpenCodeChat from '../components/OpenCodeChat';

export default function OpenCode() {
  return (
    <section className="mx-auto flex h-[calc(100dvh-7rem)] min-h-0 max-w-4xl flex-col gap-3">
      <div>
        <h1 className="text-3xl font-bold">OpenCode</h1>
        <p className="mt-1 text-sm text-gray-600">
          Chat with the agent running on this PC. Ask it to inspect or improve any project,
          pick a model below, and press Enter to send.
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <OpenCodeChat variant="page" />
      </div>
    </section>
  );
}
