import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Eye,
  FileText,
  History,
  ListChecks,
  Pencil,
  Plus,
  Printer,
  Trash2,
  Upload,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { DocumentViewer } from "@/components/DocumentViewer";
import { PrintFormsPanel } from "@/components/PrintFormsPanel";
import { ProcessNotes } from "@/components/ProcessNotes";
import { CATEGORY_LABELS, CATEGORY_ORDER, formatDate, formatDateTime } from "@/lib/constants";

function ConfirmChips({ person }) {
  const fields = [
    ["surname", "Surname"],
    ["id_number", "ID number"],
    ["date_of_birth", "Date of birth"],
  ];
  return (
    <div className="flex flex-wrap gap-1.5">
      {fields.map(([f, label]) => {
        const val = person[f];
        const has = val !== null && val !== "" && val !== undefined;
        if (!has) return null;
        const confirmed = person[`${f}_confirmed`];
        return (
          <span
            key={f}
            className={
              "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs " +
              (confirmed
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-amber-50 text-amber-800 border border-amber-200")
            }
          >
            {confirmed ? <BadgeCheck className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
            {label}
          </span>
        );
      })}
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm text-slate-900">{value || "\u2014"}</p>
    </div>
  );
}

export default function HouseholdDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [hh, setHh] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewerDoc, setViewerDoc] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [timeline, setTimeline] = useState([]);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.get(`/households/${id}/`),
      api.get(`/documents/`, { params: { household: id, page_size: 200 } }),
      api.get(`/households/${id}/timeline/`),
    ])
      .then(([h, d, t]) => {
        setHh(h.data);
        setDocs(d.data.results || d.data);
        setTimeline(t.data.results || t.data);
      })
      .catch(() => toast.error("Could not load household"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [id]);

  const openDoc = (doc) => {
    setViewerDoc(doc);
    setViewerOpen(true);
  };

  const print = async () => {
    await api.post(`/households/${id}/print/`);
    toast.success("Print action logged");
    window.print();
  };

  const deleteHousehold = async () => {
    await api.delete(`/households/${id}/`);
    toast.success("Household deleted");
    navigate("/");
  };

  const deleteMember = async (memberId) => {
    await api.delete(`/members/${memberId}/`);
    toast.success("Member removed");
    load();
  };

  const deleteDoc = async (docId) => {
    await api.delete(`/documents/${docId}/`);
    toast.success("Document removed");
    load();
  };

  if (loading) return <div className="space-y-4" data-testid="loading-state"><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (!hh) return null;

  const cg = hh.caregiver;
  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: docs.filter((d) => d.category === cat),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate("/")} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to dashboard
      </Button>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900" data-testid="household-title">
            {hh.org_household_number}
          </h1>
          <p className="text-sm text-slate-600">
            {[hh.house_number, hh.street, hh.town, hh.municipality, hh.district, hh.province]
              .filter(Boolean)
              .join(", ") || "No address captured"}
          </p>
          <p className="mt-1 text-sm text-slate-500">Registered {formatDate(hh.date_registered)}</p>
          {hh.assigned_to_names?.length > 0 && (
            <p className="mt-1 text-xs text-slate-500">Assigned to: {hh.assigned_to_names.join(", ")}</p>
          )}
          {hh.checklist_progress && (
            <div className="mt-3 max-w-xs">
              <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
                <span>Case file completeness</span>
                <span className="tabular-nums">
                  {hh.checklist_progress.yes}/{hh.checklist_progress.total} ({hh.checklist_progress.percent}%)
                </span>
              </div>
              <Progress value={hh.checklist_progress.percent} className="h-2" data-testid="household-progress" />
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="gap-2" onClick={() => navigate(`/households/${id}/checklist`)} data-testid="open-checklist-button">
            <ListChecks className="h-4 w-4" /> Checklist
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => navigate(`/households/${id}/assessment`)} data-testid="open-assessment-button">
            <FileText className="h-4 w-4" /> Assessment
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => navigate(`/documents/upload?household=${id}`)} data-testid="upload-document-button">
            <Upload className="h-4 w-4" /> Upload
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => navigate(`/households/${id}/edit`)} data-testid="edit-household-button">
            <Pencil className="h-4 w-4" /> Edit
          </Button>
          <Button variant="outline" className="gap-2" onClick={print} data-testid="print-household-button">
            <Printer className="h-4 w-4" /> Print
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="gap-2 text-rose-700 hover:text-rose-800" data-testid="delete-household-button">
                <Trash2 className="h-4 w-4" /> Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this household?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes the household, its caregiver, members, documents and checklist. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={deleteHousehold} className="bg-rose-600 hover:bg-rose-700" data-testid="confirm-delete-household-button">
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Caregiver */}
        <Card data-testid="caregiver-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Caregiver (Head of Household)</CardTitle>
            {cg ? (
              <Button variant="outline" size="sm" className="gap-1" onClick={() => navigate(`/households/${id}/caregiver`)} data-testid="edit-caregiver-button">
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
            ) : null}
          </CardHeader>
          <CardContent>
            {cg ? (
              <div className="space-y-4">
                <div>
                  <p className="text-lg font-medium text-slate-900">{cg.name} {cg.surname}</p>
                  <p className="text-sm text-slate-600">{cg.headship_type || "\u2014"}</p>
                </div>
                <ConfirmChips person={cg} />
                <div className="grid grid-cols-2 gap-3">
                  <Field label="ID type" value={cg.id_type} />
                  <Field label="ID number" value={cg.id_number} />
                  <Field label="Date of birth" value={formatDate(cg.date_of_birth)} />
                  <Field label="Sex" value={cg.sex} />
                  <Field label="Race" value={cg.race} />
                  <Field label="Marital status" value={cg.marital_status} />
                  <Field label="Cell number" value={cg.cell_number} />
                  <Field label="Home language" value={cg.home_language} />
                  <Field label="Nationality" value={cg.nationality} />
                  <Field label="Disability" value={cg.disability ? "Yes" : "No"} />
                </div>
              </div>
            ) : (
              <div className="py-6 text-center" data-testid="empty-state">
                <p className="mb-3 text-sm text-slate-600">No caregiver captured yet.</p>
                <Button className="gap-2 bg-slate-900 hover:bg-slate-800" onClick={() => navigate(`/households/${id}/caregiver`)} data-testid="add-caregiver-button">
                  <UserPlus className="h-4 w-4" /> Add caregiver
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Members */}
        <Card data-testid="members-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Household members ({hh.members?.length || 0})</CardTitle>
            <Button variant="outline" size="sm" className="gap-1" onClick={() => navigate(`/households/${id}/members/new`)} data-testid="add-member-button">
              <Plus className="h-3.5 w-3.5" /> Add
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {(!hh.members || hh.members.length === 0) && (
              <p className="py-4 text-center text-sm text-slate-600" data-testid="empty-state">No members captured yet.</p>
            )}
            {hh.members?.map((m) => (
              <div key={m.id} className="rounded-lg border border-slate-200 p-3" data-testid={`member-row-${m.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-slate-900">{m.name} {m.surname}</p>
                    <p className="text-sm text-slate-600">{m.relationship_to_head || "\u2014"} · {formatDate(m.date_of_birth)}</p>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => navigate(`/members/${m.id}/edit`)} data-testid={`edit-member-${m.id}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="icon" className="text-rose-700" data-testid={`delete-member-${m.id}`}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remove this member?</AlertDialogTitle>
                          <AlertDialogDescription>This removes {m.name} {m.surname} from the household.</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => deleteMember(m.id)} className="bg-rose-600 hover:bg-rose-700">Remove</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
                <div className="mt-2"><ConfirmChips person={m} /></div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Documents */}
      <Card data-testid="documents-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Supporting documents ({docs.length})</CardTitle>
          <Button variant="outline" size="sm" className="gap-1" onClick={() => navigate(`/documents/upload?household=${id}`)} data-testid="documents-upload-button">
            <Upload className="h-3.5 w-3.5" /> Upload
          </Button>
        </CardHeader>
        <CardContent>
          {docs.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-600" data-testid="empty-state">
              No documents uploaded yet - upload the first supporting document.
            </p>
          ) : (
            <Accordion type="multiple" defaultValue={grouped.map((g) => g.cat)} className="w-full">
              {grouped.map((g) => (
                <AccordionItem key={g.cat} value={g.cat}>
                  <AccordionTrigger className="text-sm font-medium">
                    {CATEGORY_LABELS[g.cat]} <Badge variant="secondary" className="ml-2">{g.items.length}</Badge>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {g.items.map((doc) => (
                        <div key={doc.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3" data-testid={`document-item-${doc.id}`}>
                          <div className="flex min-w-0 items-center gap-3">
                            <FileText className="h-5 w-5 shrink-0 text-slate-500" />
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-slate-900">{doc.label || doc.file_name}</p>
                              <p className="text-xs text-slate-500">{formatDate(doc.date_of_document)} · by {doc.uploaded_by}</p>
                            </div>
                          </div>
                          <div className="flex gap-1">
                            <Button variant="outline" size="sm" className="gap-1" onClick={() => openDoc(doc)} data-testid={`document-view-${doc.id}`}>
                              <Eye className="h-4 w-4" /> View
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="ghost" size="icon" className="text-rose-700" data-testid={`document-delete-${doc.id}`}>
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Remove this document?</AlertDialogTitle>
                                  <AlertDialogDescription>This permanently deletes the file.</AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => deleteDoc(doc.id)} className="bg-rose-600 hover:bg-rose-700">Remove</AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </CardContent>
      </Card>

      <ProcessNotes householdId={id} />

      <Card data-testid="household-timeline-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="h-4 w-4" /> Case history &amp; activity timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          {timeline.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-600" data-testid="timeline-empty">
              No recorded activity for this household yet.
            </p>
          ) : (
            <ol className="relative border-l-2 border-slate-200 pl-5">
              {timeline.map((e) => (
                <li key={e.id} className="mb-4 last:mb-0" data-testid={`timeline-entry-${e.id}`}>
                  <span className="absolute -left-[7px] mt-1 h-3 w-3 rounded-full bg-[color:var(--sa-green,#007a4d)]" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-700">{e.action}</span>
                    <span className="text-xs text-slate-500">{formatDateTime(e.timestamp)}</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-800">{e.target_description}</p>
                  <p className="text-xs text-slate-500">by {e.user}</p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <PrintFormsPanel householdId={id} />

      <DocumentViewer doc={viewerDoc} open={viewerOpen} onOpenChange={setViewerOpen} />
    </div>
  );
}
