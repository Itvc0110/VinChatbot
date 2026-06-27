import { AdminLayout } from "@/components/layouts/AdminLayout";

export default function AdminSegmentLayout({ children }: { children: React.ReactNode }) {
  return <AdminLayout>{children}</AdminLayout>;
}
