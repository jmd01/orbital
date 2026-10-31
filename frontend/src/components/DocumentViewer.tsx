import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, FileText, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { fetchHighlights, getDocumentUrl } from "../lib/api";
import type { Document, HighlightBox, PageJump } from "../types";
import { Button } from "./ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url,
).toString();

const MIN_WIDTH = 280;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 400;

interface DocumentViewerProps {
	document: Document | null;
	pageJump: PageJump | null;
}

export function DocumentViewer({ document, pageJump }: DocumentViewerProps) {
	const [numPages, setNumPages] = useState<number>(0);
	const [currentPage, setCurrentPage] = useState(1);
	const [pdfLoading, setPdfLoading] = useState(true);
	const [pdfError, setPdfError] = useState<string | null>(null);
	const [width, setWidth] = useState(DEFAULT_WIDTH);
	const [dragging, setDragging] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);
	const scrollRef = useRef<HTMLDivElement>(null);
	const firstHighlightRef = useRef<HTMLDivElement>(null);
	const [highlights, setHighlights] = useState<HighlightBox[]>([]);
	const [renderedPage, setRenderedPage] = useState<number | null>(null);

	// Show the requested page, and fetch where the finding's quote sits on it.
	const documentId = document?.id;

	// A different document starts at its first page. Declared before the jump effect below, so a
	// pending jump to the new document still wins.
	// biome-ignore lint/correctness/useExhaustiveDependencies: reset only when the document changes
	useEffect(() => {
		setCurrentPage(1);
	}, [documentId]);
	useEffect(() => {
		setHighlights([]);
		setRenderedPage(null);
		if (!pageJump || pageJump.documentId !== documentId) return;

		setCurrentPage(pageJump.page);
		scrollRef.current?.scrollTo({ top: 0 });

		let cancelled = false;
		fetchHighlights(pageJump.findingId)
			.then((boxes) => {
				if (!cancelled) setHighlights(boxes);
			})
			.catch(() => {
				if (!cancelled) setHighlights([]);
			});
		return () => {
			cancelled = true;
		};
	}, [pageJump, documentId]);

	// Draw the highlight only on the page it belongs to, once that page has rendered.
	const showHighlights =
		pageJump !== null &&
		currentPage === pageJump.page &&
		renderedPage === currentPage &&
		highlights.length > 0;

	// Scroll the highlight into view once, when it appears.
	useEffect(() => {
		if (showHighlights) {
			firstHighlightRef.current?.scrollIntoView({
				block: "center",
				behavior: "smooth",
			});
		}
	}, [showHighlights]);

	const handleMouseDown = useCallback(
		(e: React.MouseEvent) => {
			e.preventDefault();
			setDragging(true);

			const startX = e.clientX;
			const startWidth = width;

			const handleMouseMove = (moveEvent: MouseEvent) => {
				const delta = startX - moveEvent.clientX;
				const newWidth = Math.min(
					MAX_WIDTH,
					Math.max(MIN_WIDTH, startWidth + delta),
				);
				setWidth(newWidth);
			};

			const handleMouseUp = () => {
				setDragging(false);
				window.removeEventListener("mousemove", handleMouseMove);
				window.removeEventListener("mouseup", handleMouseUp);
			};

			window.addEventListener("mousemove", handleMouseMove);
			window.addEventListener("mouseup", handleMouseUp);
		},
		[width],
	);

	const pdfPageWidth = width - 48; // account for px-4 padding on each side

	if (!document) {
		return (
			<div
				style={{ width }}
				className="flex h-full flex-shrink-0 flex-col items-center justify-center border-l border-neutral-200 bg-neutral-50"
			>
				<FileText className="mb-3 h-10 w-10 text-neutral-300" />
				<p className="text-sm text-neutral-400">No document uploaded</p>
			</div>
		);
	}

	const pdfUrl = getDocumentUrl(document.id);

	return (
		<div
			ref={containerRef}
			style={{ width }}
			className="relative flex h-full flex-shrink-0 flex-col border-l border-neutral-200 bg-white"
		>
			{/* Resize handle */}
			<div
				className={`absolute top-0 left-0 z-10 h-full w-1.5 cursor-col-resize transition-colors hover:bg-neutral-300 ${
					dragging ? "bg-neutral-400" : ""
				}`}
				onMouseDown={handleMouseDown}
			/>

			{/* Header */}
			<div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
				<div className="min-w-0">
					<p className="truncate text-sm font-medium text-neutral-800">
						{document.filename}
					</p>
					<p className="text-xs text-neutral-400">
						{document.page_count} page{document.page_count !== 1 ? "s" : ""}
					</p>
				</div>
			</div>

			{/* PDF content */}
			<div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
				{pdfError && (
					<div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
						{pdfError}
					</div>
				)}

				<PDFDocument
					file={pdfUrl}
					onLoadSuccess={({ numPages: pages }) => {
						setNumPages(pages);
						setPdfLoading(false);
						setPdfError(null);
					}}
					onLoadError={(error) => {
						setPdfError(`Failed to load PDF: ${error.message}`);
						setPdfLoading(false);
					}}
					loading={
						<div className="flex items-center justify-center py-12">
							<Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
						</div>
					}
				>
					{!pdfLoading && !pdfError && (
						<motion.div
							key={`${currentPage}-${pageJump?.nonce ?? 0}`}
							initial={{ opacity: 0.35 }}
							animate={{ opacity: 1 }}
							transition={{ duration: 0.25 }}
						>
							<div className="relative">
								<Page
									pageNumber={currentPage}
									width={pdfPageWidth}
									onRenderSuccess={() => setRenderedPage(currentPage)}
									loading={
										<div className="flex items-center justify-center py-12">
											<Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
										</div>
									}
								/>
								{showHighlights && (
									<div className="pointer-events-none absolute inset-0">
										{highlights.map((box, index) => (
											<motion.div
												key={`${box.x0}-${box.y0}`}
												ref={index === 0 ? firstHighlightRef : undefined}
												initial={{ opacity: 0 }}
												animate={{ opacity: 1 }}
												transition={{ duration: 0.3 }}
												className="absolute rounded-sm bg-yellow-300/50 mix-blend-multiply"
												style={{
													left: `${box.x0 * 100}%`,
													top: `${box.y0 * 100}%`,
													width: `${(box.x1 - box.x0) * 100}%`,
													height: `${(box.y1 - box.y0) * 100}%`,
												}}
											/>
										))}
									</div>
								)}
							</div>
						</motion.div>
					)}
				</PDFDocument>
			</div>

			{/* Page navigation */}
			{numPages > 0 && (
				<div className="flex items-center justify-center gap-3 border-t border-neutral-100 px-4 py-2.5">
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={currentPage <= 1}
						onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
					>
						<ChevronLeft className="h-4 w-4" />
					</Button>
					<span className="text-xs text-neutral-500">
						Page {currentPage} of {numPages}
					</span>
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={currentPage >= numPages}
						onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
					>
						<ChevronRight className="h-4 w-4" />
					</Button>
				</div>
			)}
		</div>
	);
}
