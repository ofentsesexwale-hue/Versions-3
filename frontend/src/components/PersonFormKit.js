import { useState } from "react";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ChoiceSelect({ label, value, onChange, options, testId }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger className="h-11" data-testid={testId}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o} value={o}>
              {o}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export function usePersonForm(initial) {
  const [form, setForm] = useState(initial);
  const [confirmed, setConfirmed] = useState({
    surname: false,
    id_number: false,
    date_of_birth: false,
  });
  const [meta, setMeta] = useState({});
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setConfirmable = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }));
    setConfirmed((c) => ({ ...c, [k]: false })); // changing value reverts confirmation
  };
  const hasVal = (k) => {
    const v = form[k];
    return v !== null && v !== undefined && String(v).trim() !== "";
  };
  const blocked = ["surname", "id_number", "date_of_birth"].some(
    (k) => hasVal(k) && !confirmed[k]
  );
  return { form, setForm, set, confirmed, setConfirmed, setConfirmable, meta, setMeta, hasVal, blocked };
}
