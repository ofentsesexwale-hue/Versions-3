export default function LaunchScreen({ message = "Opening the office file…" }) {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#f3ead8] px-6"
      data-testid="app-launch-screen"
    >
      <div className="h-36 w-36 overflow-hidden rounded-[28px] bg-[#f7f0e4] shadow-[0_12px_40px_rgba(63,58,50,0.18)]">
        <img src="/emblem.jpg" alt="Sebueng Itumeleng" className="h-full w-full object-cover" />
      </div>
      <h1 className="text-[22px] font-semibold tracking-tight text-[#3f3a32]">OVC CaseFile</h1>
      <p className="text-sm text-[#7a7368]">Sebueng Itumeleng</p>
      <p className="text-sm text-[#5c564c]">{message}</p>
      <div className="h-[5px] w-52 overflow-hidden rounded-full bg-black/10">
        <div className="ovc-launch-bar h-full w-[38%] rounded-full bg-[#3f3a32]" />
      </div>
    </div>
  );
}
