import { useEffect, useId, useRef, useState } from 'react'

export type ComboboxOption = {
  value: string
  label: string
  disabled?: boolean
  healthStatus?: 'online' | 'degraded' | 'offline' | 'unknown'
  healthLabel?: string
  detail?: string
}

type ContextComboboxProps = {
  label: string
  value: string
  options: ComboboxOption[]
  onChange: (value: string) => void
  allLabel?: string
  emptyLabel?: string
  disabled?: boolean
  searchable?: boolean
  name?: string
  className?: string
}

export default function ContextCombobox({
  label,
  value,
  options,
  onChange,
  allLabel,
  emptyLabel = 'No matching options',
  disabled = false,
  searchable = false,
  name,
  className = '',
}: ContextComboboxProps) {
  const id = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const allOption: ComboboxOption[] = allLabel === undefined ? [] : [{ value: '', label: allLabel }]
  const availableOptions = [...allOption, ...options]
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filteredOptions = searchable
    ? availableOptions.filter((option) => option.label.toLocaleLowerCase().includes(normalizedQuery))
    : availableOptions
  const selectedOption = availableOptions.find((option) => option.value === value) ?? availableOptions[0]

  useEffect(() => {
    const closeOnOutsidePointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close()
    }
    document.addEventListener('mousedown', closeOnOutsidePointer)
    return () => document.removeEventListener('mousedown', closeOnOutsidePointer)
  }, [])

  useEffect(() => setActiveIndex(0), [query, isOpen])

  function close() {
    setIsOpen(false)
    setQuery('')
  }

  function open() {
    if (!disabled) setIsOpen(true)
  }

  function selectOption(option: ComboboxOption) {
    if (option.disabled) return
    onChange(option.value)
    close()
    inputRef.current?.focus()
  }

  function moveActive(direction: 1 | -1) {
    const enabledOptions = filteredOptions.map((option, index) => option.disabled ? -1 : index).filter((index) => index >= 0)
    if (!enabledOptions.length) return
    setActiveIndex((current) => {
      const position = enabledOptions.indexOf(current)
      return enabledOptions[(position + direction + enabledOptions.length) % enabledOptions.length]
    })
  }

  return (
    <div ref={rootRef} className={`context-combobox ${className}`} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) close()
    }}>
      {name && <input type="hidden" name={name} value={value} />}
      <input
        ref={inputRef}
        aria-activedescendant={isOpen && filteredOptions[activeIndex] ? `${id}-option-${activeIndex}` : undefined}
        aria-autocomplete={searchable ? 'list' : 'none'}
        aria-controls={`${id}-listbox`}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={label}
        autoComplete="off"
        className="context-combobox-input"
        disabled={disabled}
        onChange={(event) => {
          if (!searchable) return
          setQuery(event.target.value)
          open()
        }}
        onClick={open}
        onFocus={open}
        onKeyDown={(event) => {
          if (event.key === 'Escape') return close()
          if (event.key === 'Tab') return close()
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            const wasOpen = isOpen
            open()
            if (!wasOpen) setActiveIndex(event.key === 'ArrowDown' ? 0 : filteredOptions.length - 1)
            else moveActive(event.key === 'ArrowDown' ? 1 : -1)
            return
          }
          if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault()
            open()
            setActiveIndex(event.key === 'Home' ? 0 : Math.max(filteredOptions.length - 1, 0))
            return
          }
          if ((event.key === 'Enter' || event.key === ' ') && isOpen && filteredOptions[activeIndex]) {
            event.preventDefault()
            selectOption(filteredOptions[activeIndex])
          }
        }}
        readOnly={!searchable}
        role="combobox"
        value={isOpen && searchable ? query : selectedOption?.label ?? ''}
        style={{ paddingRight: !isOpen && !searchable && selectedOption?.healthStatus ? '2.8rem' : undefined }}
      />
      {!isOpen && !searchable && selectedOption?.healthStatus && <span className={`health-badge health-${selectedOption.healthStatus}`} style={{ position:'absolute', top:'50%', right:'1.35rem', transform:'translateY(-50%)', zIndex:1, pointerEvents:'none', lineHeight:'1' }}>{selectedOption.healthLabel ?? selectedOption.healthStatus}</span>}
      <span aria-hidden="true" className="context-combobox-chevron" />
      {isOpen && <div id={`${id}-listbox`} className="context-combobox-options" role="listbox" aria-label={label}>
        {filteredOptions.map((option, index) => <button
          id={`${id}-option-${index}`}
          aria-selected={option.value === value}
          className={`context-combobox-option${index === activeIndex ? ' is-active' : ''}`}
          disabled={option.disabled}
          key={option.value || 'all'}
          onMouseEnter={() => !option.disabled && setActiveIndex(index)}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => selectOption(option)}
          role="option"
          type="button"
        ><span>{option.label}</span>{option.healthStatus && <span className={`health-badge health-${option.healthStatus}`}>{option.healthLabel ?? option.healthStatus}{option.detail && ` · ${option.detail}`}</span>}</button>)}
        {!filteredOptions.length && <p className="context-combobox-empty" role="status">{emptyLabel}</p>}
      </div>}
    </div>
  )
}
