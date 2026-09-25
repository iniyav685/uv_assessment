import FormatBold from '@mui/icons-material/FormatBold'
import FormatItalic from '@mui/icons-material/FormatItalic'
import FormatListBulleted from '@mui/icons-material/FormatListBulleted'
import FormatListNumbered from '@mui/icons-material/FormatListNumbered'
import FormatQuote from '@mui/icons-material/FormatQuote'
import FormatStrikethrough from '@mui/icons-material/FormatStrikethrough'
import FormatUnderlined from '@mui/icons-material/FormatUnderlined'
import InsertLink from '@mui/icons-material/InsertLink'
import CodeIcon from '@mui/icons-material/Code'
import {
  Box,
  Button,
  Divider,
  IconButton,
  Popover,
  Stack,
  TextField,
  Tooltip,
  type SxProps,
  type Theme,
} from '@mui/material'
import { Placeholder } from '@tiptap/extensions'
import { EditorContent, useEditor, useEditorState, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import {
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from 'react'

export interface RichTextEditorHandle {
  clear: () => void
  focus: () => void
}

interface Props {
  ref?: Ref<RichTextEditorHandle>
  placeholder?: string
  disabled?: boolean
  ariaLabel: string
  error?: boolean
  /** Initial HTML. Only read once, at creation — remount the component (e.g. via `key`) to reset it. */
  content?: string
  /** Called with the editor's HTML and whether it has any visible text. */
  onChange: (html: string, isEmpty: boolean) => void
  /** Ctrl/Cmd + Enter. */
  onSubmitShortcut?: () => void
  /** Extra controls rendered at the right end of the toolbar (e.g. attach button). */
  toolbarEnd?: ReactNode
  sx?: SxProps<Theme>
}

/** TipTap-based rich text editor with an MUI toolbar. Output is HTML (sanitised server-side). */
export default function RichTextEditor({
  ref,
  placeholder = 'Write something…',
  disabled = false,
  ariaLabel,
  error = false,
  content,
  onChange,
  onSubmitShortcut,
  toolbarEnd,
  sx,
}: Props) {
  // Callbacks go through refs so the editor is created exactly once; re-creating it
  // on every render would drop keystrokes and invalidate the instance.
  const onChangeRef = useRef(onChange)
  const onSubmitRef = useRef(onSubmitShortcut)
  useLayoutEffect(() => {
    onChangeRef.current = onChange
    onSubmitRef.current = onSubmitShortcut
  })

  const editor = useEditor(
    {
      content,
      extensions: [
        StarterKit.configure({
          heading: { levels: [2, 3] },
          horizontalRule: false,
          codeBlock: false,
          link: { openOnClick: false, autolink: true, defaultProtocol: 'https' },
        }),
        Placeholder.configure({ placeholder }),
      ],
      editorProps: {
        attributes: { 'aria-label': ariaLabel, 'aria-multiline': 'true', role: 'textbox' },
        handleKeyDown: (_view, event) => {
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && onSubmitRef.current) {
            onSubmitRef.current()
            return true
          }
          return false
        },
      },
      onUpdate: ({ editor: e }) =>
        onChangeRef.current(e.getHTML(), e.isEmpty || !e.getText().trim()),
    },
    [],
  )

  useEffect(() => {
    editor?.setEditable(!disabled)
  }, [editor, disabled])

  useImperativeHandle(
    ref,
    () => ({
      clear: () => editor?.commands.clearContent(true),
      focus: () => editor?.commands.focus(),
    }),
    [editor],
  )

  return (
    <Box
      sx={[
        {
          border: 1,
          borderColor: error ? 'error.main' : 'divider',
          borderRadius: 1,
          bgcolor: 'background.paper',
          '&:focus-within': { borderColor: error ? 'error.main' : 'primary.main' },
          '& .tiptap': {
            minHeight: 44,
            maxHeight: 220,
            overflowY: 'auto',
            px: 1.5,
            py: 1,
            outline: 'none',
            typography: 'body2',
            '& p': { m: 0 },
            '& ul, & ol': { my: 0.5, pl: 3 },
            '& blockquote': { borderLeft: 3, borderColor: 'divider', m: 0, pl: 1.5, color: 'text.secondary' },
            '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontSize: '0.85em' },
            '& p.is-editor-empty:first-of-type::before': {
              content: 'attr(data-placeholder)',
              color: 'text.disabled',
              float: 'left',
              height: 0,
              pointerEvents: 'none',
            },
          },
        },
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      {editor && <Toolbar editor={editor} disabled={disabled} end={toolbarEnd} />}
      <EditorContent editor={editor} />
    </Box>
  )
}

function Toolbar({ editor, disabled, end }: { editor: Editor; disabled: boolean; end?: ReactNode }) {
  // Subscribe only to the formatting state the toolbar shows, not every keystroke.
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e.isActive('bold'),
      italic: e.isActive('italic'),
      underline: e.isActive('underline'),
      strike: e.isActive('strike'),
      code: e.isActive('code'),
      bulletList: e.isActive('bulletList'),
      orderedList: e.isActive('orderedList'),
      blockquote: e.isActive('blockquote'),
      link: e.isActive('link'),
    }),
  })
  const chain = () => editor.chain().focus()

  const buttons = [
    { key: 'bold', label: 'Bold', icon: <FormatBold />, run: () => chain().toggleBold().run() },
    { key: 'italic', label: 'Italic', icon: <FormatItalic />, run: () => chain().toggleItalic().run() },
    { key: 'underline', label: 'Underline', icon: <FormatUnderlined />, run: () => chain().toggleUnderline().run() },
    { key: 'strike', label: 'Strikethrough', icon: <FormatStrikethrough />, run: () => chain().toggleStrike().run() },
    { key: 'code', label: 'Inline code', icon: <CodeIcon />, run: () => chain().toggleCode().run() },
    { key: 'bulletList', label: 'Bulleted list', icon: <FormatListBulleted />, run: () => chain().toggleBulletList().run() },
    { key: 'orderedList', label: 'Numbered list', icon: <FormatListNumbered />, run: () => chain().toggleOrderedList().run() },
    { key: 'blockquote', label: 'Quote', icon: <FormatQuote />, run: () => chain().toggleBlockquote().run() },
  ] as const

  return (
    <Stack
      direction="row"
      role="toolbar"
      aria-label="Formatting"
      sx={{ alignItems: 'center', px: 0.5, py: 0.25, borderBottom: 1, borderColor: 'divider', flexWrap: 'wrap' }}
    >
      {buttons.map((b) => (
        <Tooltip key={b.key} title={b.label}>
          <span>
            <IconButton
              size="small"
              aria-label={b.label}
              aria-pressed={state[b.key]}
              color={state[b.key] ? 'primary' : 'default'}
              // Keep focus and selection in the editor when clicking a toolbar button.
              onMouseDown={(e) => e.preventDefault()}
              onClick={b.run}
              disabled={disabled}
            >
              {b.icon}
            </IconButton>
          </span>
        </Tooltip>
      ))}
      <LinkButton editor={editor} active={state.link} disabled={disabled} />
      {end && (
        <>
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5, my: 0.5 }} />
          {end}
        </>
      )}
    </Stack>
  )
}

function LinkButton({ editor, active, disabled }: { editor: Editor; active: boolean; disabled: boolean }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [url, setUrl] = useState('')

  function apply() {
    const href = url.trim()
    const chain = editor.chain().focus().extendMarkRange('link')
    if (!href) chain.unsetLink().run()
    else chain.setLink({ href: /^(https?:|mailto:)/i.test(href) ? href : `https://${href}` }).run()
    setAnchor(null)
  }

  return (
    <>
      <Tooltip title="Link">
        <span>
          <IconButton
            size="small"
            aria-label="Link"
            aria-pressed={active}
            color={active ? 'primary' : 'default'}
            disabled={disabled}
            onClick={(e) => {
              setUrl(editor.getAttributes('link').href ?? '')
              setAnchor(e.currentTarget)
            }}
          >
            <InsertLink />
          </IconButton>
        </span>
      </Tooltip>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Stack
          component="form"
          direction="row"
          spacing={1}
          sx={{ p: 1.5 }}
          onSubmit={(e) => {
            e.preventDefault()
            apply()
          }}
        >
          <TextField
            size="small"
            autoFocus
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            slotProps={{ htmlInput: { 'aria-label': 'Link URL' } }}
          />
          <Button type="submit" variant="contained" size="small">
            {url.trim() ? 'Apply' : 'Remove'}
          </Button>
        </Stack>
      </Popover>
    </>
  )
}
