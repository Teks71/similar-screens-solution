import unittest

from contracts.dto import MinioObjectReference, SimilarRequest, SimilarResponse, SimilarResult


class SimilarContractsTest(unittest.TestCase):
    def test_request_includes_top_k_and_source(self) -> None:
        reference = MinioObjectReference(bucket="screens", object_key="original.png")
        request = SimilarRequest(source=reference, top_k=5)

        self.assertEqual(request.source.bucket, "screens")
        self.assertEqual(request.top_k, 5)

    def test_response_contains_result_metadata(self) -> None:
        reference = MinioObjectReference(bucket="screens", object_key="match.png")
        result = SimilarResult(
            score=0.87,
            title="Close match",
            url="http://example.com/match.png",
            object=reference,
        )
        response = SimilarResponse(results=[result])

        self.assertEqual(len(response.results), 1)
        self.assertAlmostEqual(response.results[0].score, 0.87)
        self.assertEqual(response.results[0].object.object_key, "match.png")


if __name__ == "__main__":
    unittest.main()
