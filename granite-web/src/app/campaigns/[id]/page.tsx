'use client';

import { useParams, useRouter } from 'next/navigation';
import { CampaignDashboard } from '@/components/campaigns/CampaignDashboard';

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = parseInt(params.id as string);

  return (
    <CampaignDashboard
      campaignId={id}
      onClose={() => router.push('/campaigns')}
    />
  );
}
