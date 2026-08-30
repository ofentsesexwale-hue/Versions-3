import { Printer, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DSD_FORMS, printForm } from "@/lib/print";

// Groups the DSD forms and renders a print button for each, scoped to one household.
export function PrintFormsPanel({ householdId }) {
  const groups = DSD_FORMS.reduce((acc, f) => {
    (acc[f.group] = acc[f.group] || []).push(f);
    return acc;
  }, {});

  return (
    <Card data-testid="dsd-forms-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <Printer className="h-4 w-4" /> DSD Forms &amp; Printing
        </CardTitle>
        <Button
          className="gap-2 bg-slate-900 hover:bg-slate-800"
          onClick={() => printForm("full", { householdId })}
          data-testid="print-full-casefile-button"
        >
          <FileText className="h-4 w-4" /> Print Full Case File
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-slate-500">
          Each form opens as an official DSD-formatted, print-ready page. Use your browser's
          print dialog to print to paper or save as PDF.
        </p>
        {Object.entries(groups).map(([group, forms]) => (
          <div key={group}>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">{group}</p>
            <div className="flex flex-wrap gap-2">
              {forms.map((f) => (
                <Button
                  key={f.key}
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => printForm(f.key, { householdId })}
                  data-testid={`print-form-${f.key}`}
                >
                  <Printer className="h-3.5 w-3.5" /> {f.label}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
