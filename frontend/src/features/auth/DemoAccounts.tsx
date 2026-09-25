import { Chip, Divider, Stack, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { authService } from '@/services/auth.service'

/** One-click demo logins, served only when the backend runs with DEMO_MODE. */
export default function DemoAccounts({ onPick }: { onPick: (username: string, password: string) => void }) {
  const { data } = useQuery({
    queryKey: ['auth', 'demo-accounts'],
    queryFn: authService.getDemoAccounts,
    staleTime: Infinity,
    retry: false,
  })
  if (!data?.enabled || !data.accounts.length) return null

  return (
    <>
      <Divider sx={{ my: 3 }}>
        <Typography variant="caption" color="text.secondary">
          Demo accounts
        </Typography>
      </Divider>
      <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
        {data.accounts.map((a) => (
          <Chip
            key={a.username}
            label={a.display_name}
            variant="outlined"
            onClick={() => onPick(a.username, data.password ?? '')}
            aria-label={`Fill in ${a.display_name}, ${a.role_label}`}
          />
        ))}
      </Stack>
    </>
  )
}
