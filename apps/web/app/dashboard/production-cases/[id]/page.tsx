import ProductionCaseDetailPage from '@/app/admin/production-cases/[id]/page'
import { ProductionWorkspace } from '@/components/production/ProductionWorkspace'

export default function ManagerProductionCaseDetailPage() {
  return <ProductionWorkspace><ProductionCaseDetailPage /></ProductionWorkspace>
}
