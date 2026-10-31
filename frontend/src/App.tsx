import { useCallback, useState } from "react";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import { DocumentViewer } from "./components/DocumentViewer";
import { RiskReviewPage } from "./components/RiskReviewPage";
import { TooltipProvider } from "./components/ui/tooltip";
import { useConversations } from "./hooks/use-conversations";
import { useDocument } from "./hooks/use-document";
import { useMessages } from "./hooks/use-messages";
import { useReview, useReviews } from "./hooks/use-reviews";
import type { Finding, PageJump } from "./types";

export default function App() {
	const {
		conversations,
		selectedId,
		loading: conversationsLoading,
		create,
		select,
		remove,
		refresh: refreshConversations,
	} = useConversations();

	const {
		messages,
		loading: messagesLoading,
		error: messagesError,
		streaming,
		streamingContent,
		streamingRiskTable,
		reviewing,
		send,
	} = useMessages(selectedId);

	const {
		document,
		upload,
		refresh: refreshDocument,
	} = useDocument(selectedId);

	// Which risk review is open as the main panel; null means the selected chat is shown.
	const [reviewId, setReviewId] = useState<string | null>(null);
	const { reviews, refresh: refreshReviews } = useReviews();
	const {
		review,
		loading: reviewLoading,
		error: reviewError,
	} = useReview(reviewId);

	// The reader shows the open review's document, otherwise the selected chat's.
	const viewerDocument = reviewId ? (review?.document ?? null) : document;

	const [pageJump, setPageJump] = useState<PageJump | null>(null);

	const handleViewFinding = useCallback(
		(finding: Finding) => {
			if (viewerDocument && finding.page !== null) {
				setPageJump({
					documentId: viewerDocument.id,
					page: finding.page,
					findingId: finding.id,
					nonce: Date.now(),
				});
			}
		},
		[viewerDocument],
	);

	const handleSend = useCallback(
		async (content: string) => {
			await send(content);
			refreshConversations();
			refreshReviews();
		},
		[send, refreshConversations, refreshReviews],
	);

	const handleUpload = useCallback(
		async (file: File) => {
			const doc = await upload(file);
			if (doc) {
				refreshDocument();
				refreshConversations();
			}
		},
		[upload, refreshDocument, refreshConversations],
	);

	const handleCreate = useCallback(async () => {
		setReviewId(null);
		await create();
	}, [create]);

	const handleSelectConversation = useCallback(
		(id: string | null) => {
			setReviewId(null);
			select(id);
		},
		[select],
	);

	const handleDelete = useCallback(
		async (id: string) => {
			await remove(id);
			if (review?.conversation_id === id) setReviewId(null);
			refreshReviews();
		},
		[remove, review, refreshReviews],
	);

	return (
		<TooltipProvider delayDuration={200}>
			<div className="flex h-screen bg-neutral-50">
				<ChatSidebar
					conversations={conversations}
					selectedId={reviewId ? null : selectedId}
					loading={conversationsLoading}
					onSelect={handleSelectConversation}
					onCreate={handleCreate}
					onDelete={handleDelete}
					reviews={reviews}
					selectedReviewId={reviewId}
					onSelectReview={setReviewId}
				/>

				{reviewId ? (
					<RiskReviewPage
						review={review}
						loading={reviewLoading}
						error={reviewError}
						onViewFinding={handleViewFinding}
						onOpenConversation={handleSelectConversation}
					/>
				) : (
					<ChatWindow
						messages={messages}
						loading={messagesLoading}
						error={messagesError}
						streaming={streaming}
						streamingContent={streamingContent}
						streamingRiskTable={streamingRiskTable}
						reviewing={reviewing}
						hasDocument={!!document}
						conversationId={selectedId}
						onSend={handleSend}
						onUpload={handleUpload}
						onViewFinding={handleViewFinding}
					/>
				)}

				<DocumentViewer document={viewerDocument} pageJump={pageJump} />
			</div>
		</TooltipProvider>
	);
}
