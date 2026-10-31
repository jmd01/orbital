import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { ReviewDetail, ReviewSummary } from "../types";

// The latest risk review of each document, for the sidebar list.
export function useReviews() {
	const [reviews, setReviews] = useState<ReviewSummary[]>([]);

	const refresh = useCallback(async () => {
		try {
			setReviews(await api.fetchReviews());
		} catch {
			// The list is a convenience; a failed refresh leaves the previous one in place.
		}
	}, []);

	useEffect(() => {
		refresh();
	}, [refresh]);

	return { reviews, refresh };
}

// One review in full, for the full-page view.
export function useReview(reviewId: string | null) {
	const [review, setReview] = useState<ReviewDetail | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		setReview(null);
		setError(null);
		if (!reviewId) return;

		let cancelled = false;
		setLoading(true);
		api
			.fetchReview(reviewId)
			.then((data) => {
				if (!cancelled) setReview(data);
			})
			.catch((err) => {
				if (!cancelled) {
					setError(
						err instanceof Error ? err.message : "Failed to load review",
					);
				}
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [reviewId]);

	return { review, loading, error };
}
