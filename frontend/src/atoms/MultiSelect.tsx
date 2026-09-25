import { Autocomplete, TextField } from '@mui/material'

export interface MultiSelectOption<V> {
  value: V
  label: string
}

interface Props<V> {
  label: string
  options: MultiSelectOption<V>[]
  value: V[]
  onChange: (v: V[]) => void
}

export default function MultiSelect<V extends string | number>({
  label,
  options,
  value,
  onChange,
}: Props<V>) {
  return (
    <Autocomplete
      multiple
      size="small"
      options={options}
      value={options.filter((o) => value.includes(o.value))}
      onChange={(_, selected) => onChange(selected.map((o) => o.value))}
      getOptionLabel={(o) => o.label}
      isOptionEqualToValue={(a, b) => a.value === b.value}
      disableCloseOnSelect
      renderInput={(params) => <TextField {...params} label={label} placeholder="Any" />}
    />
  )
}
