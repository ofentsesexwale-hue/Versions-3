import { useEffect, useState } from "react";
import { Download, FileText, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { fetchFileObjectUrl } from "@/lib/api";

/** View-only document viewer. No edit/annotate affordances. */
export function DocumentViewer({ doc, open, onOpenChange }) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let revoked = null;
    if (open && doc) {
      setLoading(true);
      setError(false);
      fetchFileObjectUrl(doc.view_url)
        .then((url) => {
          revoked = url;
          setObjectUrl(url);
        })
        .catch(() => setError(true))
        .finally(() => setLoading(false));
    }
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
      setObjectUrl(null);
    };
  }, [open, doc]);

  const download = async () => {
    const url = await fetchFileObjectUrl(doc.download_url);
    const a = document.createElement("a");
    a.href = url;
    a.download = doc.file_name || "document";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!doc) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-4xl h-[85vh] flex flex-col"
        data-testid="document-viewer-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileText className="h-5 w-5" />
            <span className="truncate">{doc.label || doc.file_name}</span>
          </DialogTitle>
          <p className="text-sm text-slate-600">{doc.category_display}</p>
        </DialogHeader>
        <div className="flex-1 overflow-auto rounded-md border border-slate-200 bg-slate-100">
          {loading && (
            <div className="flex h-full items-center justify-center text-slate-600">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading document...
            </div>
          )}
          {error && (
            <div className="flex h-full items-center justify-center text-rose-700" data-testid="error-alert">
              We couldn't load this file.
            </div>
          )}
          {!loading && !error && objectUrl && doc.is_pdf && (
            <iframe title="document" src={objectUrl} className="h-full w-full" />
          )}
          {!loading && !error && objectUrl && !doc.is_pdf && (
            <div className="flex h-full items-center justify-center p-4">
              <img src={objectUrl} alt={doc.label} className="max-h-full max-w-full object-contain" />
            </div>
          )}
        </div>
        <div className="flex justify-end">
          <Button variant="outline" onClick={download} data-testid="document-download-button" className="gap-2">
            <Download className="h-4 w-4" /> Download original
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
