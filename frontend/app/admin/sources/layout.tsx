import { SourcesTopNav } from "@/components/admin/SourcesTopNav";

export default function SourcesSegmentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="admin-sources-section">
      <SourcesTopNav />
      {children}
    </div>
  );
}
