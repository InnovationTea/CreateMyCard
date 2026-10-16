import { useEffect, useState } from 'react';
import type { ServiceConfigField } from '../batchApi';

type Props = {
  field: ServiceConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
  onValidity?: (valid: boolean) => void;
};

export function ServiceConfigInput({ field, value, onChange, onValidity }: Props) {
  const complex = ['dict', 'list', 'tuple'].includes(field.type) || value === null;
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    setText(complex ? JSON.stringify(value, null, 2) : String(value ?? ''));
    setError('');
  }, [value, complex]);
  if (!field.editable) {
    return <div className="service-config-readonly" title={field.readOnlyReason}>{!field.sensitive && <pre title={typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}</pre>}<small>{field.readOnlyReason}</small></div>;
  }
  if (field.type === 'bool') {
    return <input aria-label={field.displayName} type="checkbox" checked={value === true} onChange={(event) => onChange(event.target.checked)} />;
  }
  const edit = (next: string) => {
    setText(next);
    try {
      let parsed: unknown = next;
      if (complex) parsed = JSON.parse(next);
      if (['int', 'float'].includes(field.type)) {
        if (!next.trim() || !Number.isFinite(Number(next))) throw new Error('请输入有效数值');
        parsed = Number(next);
        if (field.type === 'int' && !Number.isInteger(parsed)) throw new Error('请输入整数');
      }
      setError('');
      onValidity?.(true);
      onChange(parsed);
    } catch (reason) {
      setError(complex ? '请输入合法 JSON' : String(reason));
      onValidity?.(false);
    }
  };
  return <div className="service-config-value">
    {complex || text.includes('\n') || field.name.endsWith('system_prompt')
      ? <textarea aria-label={field.displayName} value={text} onChange={(event) => edit(event.target.value)} onBlur={(event) => { event.currentTarget.scrollTop = 0; event.currentTarget.scrollLeft = 0; }} rows={4} />
      : <input aria-label={field.displayName} type={['int', 'float'].includes(field.type) ? 'number' : 'text'} value={text} onChange={(event) => edit(event.target.value)} />}
    {error && <small role="alert">{error}</small>}
  </div>;
}
