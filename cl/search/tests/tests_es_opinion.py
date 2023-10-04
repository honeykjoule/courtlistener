import datetime

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import AsyncRequestFactory, override_settings
from django.urls import reverse
from django.utils.timezone import now
from factory import RelatedFactory
from lxml import html
from rest_framework.status import HTTP_200_OK
from waffle.testutils import override_flag

from cl.lib.test_helpers import (
    CourtTestCase,
    EmptySolrTestCase,
    IndexedSolrTestCase,
    PeopleTestCase,
    SearchTestCase,
)
from cl.search.documents import (
    ES_CHILD_ID,
    OpinionClusterDocument,
    OpinionDocument,
)
from cl.search.factories import (
    CitationWithParentsFactory,
    CourtFactory,
    DocketFactory,
    OpinionClusterFactory,
    OpinionClusterFactoryWithChildrenAndParents,
    OpinionFactory,
    OpinionWithChildrenFactory,
)
from cl.search.models import PRECEDENTIAL_STATUS, SEARCH_TYPES
from cl.search.views import do_search
from cl.tests.cases import ESIndexTestCase, TestCase
from cl.users.factories import UserProfileWithParentsFactory


class OpinionsSearchTest(
    ESIndexTestCase, CourtTestCase, PeopleTestCase, SearchTestCase, TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.rebuild_index("search.OpinionCluster")
        super().setUpTestData()
        court = CourtFactory(
            id="canb",
            jurisdiction="FB",
            full_name="court of the Medical Worries",
        )
        OpinionClusterFactoryWithChildrenAndParents(
            case_name="Strickland v. Washington.",
            case_name_full="Strickland v. Washington.",
            docket=DocketFactory(court=court, docket_number="1:21-cv-1234"),
            sub_opinions=RelatedFactory(
                OpinionWithChildrenFactory,
                factory_related_name="cluster",
                html_columbia="<p>Code, &#167; 1-815</p>",
            ),
            date_filed=datetime.date(2020, 8, 15),
            precedential_status=PRECEDENTIAL_STATUS.PUBLISHED,
            syllabus="some rando syllabus",
            procedural_history="some rando history",
            source="C",
            judges="",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            citation_count=1,
            scdb_votes_minority=3,
            scdb_votes_majority=6,
        )
        OpinionClusterFactoryWithChildrenAndParents(
            case_name="Strickland v. Lorem.",
            case_name_full="Strickland v. Lorem.",
            date_filed=datetime.date(2020, 8, 15),
            docket=DocketFactory(court=court, docket_number="123456"),
            precedential_status=PRECEDENTIAL_STATUS.PUBLISHED,
            syllabus="some rando syllabus",
            procedural_history="some rando history",
            source="C",
            judges="",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            citation_count=1,
            scdb_votes_minority=3,
            scdb_votes_majority=6,
        )

    async def _test_article_count(self, params, expected_count, field_name):
        r = await self.async_client.get("/", params)
        tree = html.fromstring(r.content.decode())
        got = len(tree.xpath("//article"))
        self.assertEqual(
            got,
            expected_count,
            msg="Did not get the right number of search results in Frontend with %s "
            "filter applied.\n"
            "Expected: %s\n"
            "     Got: %s\n\n"
            "Params were: %s" % (field_name, expected_count, got, params),
        )
        return r

    async def _test_api_results_count(
        self, params, expected_count, field_name
    ):
        """Get the result count in a API query response"""
        r = await self.async_client.get(
            reverse("search-list", kwargs={"version": "v3"}), params
        )
        got = len(r.data["results"])
        self.assertEqual(
            got,
            expected_count,
            msg="Did not get the right number of search results in API with %s "
            "filter applied.\n"
            "Expected: %s\n"
            "     Got: %s\n\n"
            "Params were: %s" % (field_name, expected_count, got, params),
        )
        return r

    def test_remove_parent_child_objects_from_index(self) -> None:
        """Confirm join child objects are removed from the index when the
        parent objects is deleted.
        """
        cluster = OpinionClusterFactory.create(
            case_name_full="Paul Debbas v. Franklin",
            case_name_short="Debbas",
            syllabus="some rando syllabus",
            date_filed=datetime.date(2015, 8, 14),
            procedural_history="some rando history",
            source="C",
            case_name="Debbas v. Franklin",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            precedential_status="Errata",
            citation_count=4,
            docket=self.docket_1,
        )
        opinion_1 = OpinionFactory.create(
            extracted_by_ocr=False,
            author=self.person_2,
            plain_text="my plain text",
            cluster=cluster,
            local_path="test/search/opinion_doc1.doc",
            per_curiam=False,
            type="010combined",
        )

        cluster_pk = cluster.pk
        opinion_pk = opinion_1.pk
        # Cluster instance is indexed.
        self.assertTrue(OpinionClusterDocument.exists(id=cluster_pk))
        # Opinion instance is indexed.
        self.assertTrue(
            OpinionDocument.exists(id=ES_CHILD_ID(opinion_pk).OPINION)
        )

        # Delete Cluster instance; it should be removed from the index along
        # with its child documents.
        cluster.delete()

        # Cluster document should be removed.
        self.assertFalse(OpinionClusterDocument.exists(id=cluster_pk))
        # Opinion document is removed.
        self.assertFalse(
            OpinionDocument.exists(id=ES_CHILD_ID(opinion_pk).OPINION)
        )

    def test_remove_nested_objects_from_index(self) -> None:
        """Confirm that child objects are removed from the index when they are
        deleted independently of their parent object
        """
        cluster = OpinionClusterFactory.create(
            case_name_full="Paul Debbas v. Franklin",
            case_name_short="Debbas",
            syllabus="some rando syllabus",
            date_filed=datetime.date(2015, 8, 14),
            procedural_history="some rando history",
            source="C",
            case_name="Debbas v. Franklin",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            precedential_status="Errata",
            citation_count=4,
            docket=self.docket_1,
        )
        opinion_1 = OpinionFactory.create(
            extracted_by_ocr=False,
            author=self.person_2,
            plain_text="my plain text",
            cluster=cluster,
            local_path="test/search/opinion_doc1.doc",
            per_curiam=False,
            type="010combined",
        )

        cluster_pk = cluster.pk
        opinion_pk = opinion_1.pk

        # Delete pos_1 and education, keep the parent person instance.
        opinion_1.delete()

        # Opinion cluster instance still exists.
        self.assertTrue(OpinionClusterDocument.exists(id=cluster_pk))

        # Opinion object is removed
        self.assertFalse(
            OpinionDocument.exists(id=ES_CHILD_ID(opinion_pk).OPINION)
        )
        cluster.delete()

    def test_child_document_update_properly(self) -> None:
        """Confirm that child fields are properly update when changing DB records"""
        opinion = OpinionFactory.create(
            extracted_by_ocr=False,
            author=self.person_1,
            plain_text="my plain text secret word for queries",
            cluster=self.opinion_cluster_1,
            local_path="test/search/opinion_doc.doc",
            per_curiam=False,
            type="020lead",
        )
        # Update the author field in the opinion record.
        opinion.author = self.person_2
        opinion.save()

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(es_doc.author_id, self.person_2.pk)

        # Update the type field in the opinion record.
        opinion.type = "010combined"
        opinion.save()

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(es_doc.type, "010combined")
        self.assertEqual(es_doc.type_text, "Combined Opinion")

        # Update the per_curiam field in the opinion record.
        opinion.per_curiam = True
        opinion.save()

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(es_doc.per_curiam, True)

        # Update the text field in the opinion record.
        opinion.plain_text = "This is a test"
        opinion.save()

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(es_doc.text, "This is a test")

        # Update cites field in the opinion record.
        opinion.opinions_cited.add(self.opinion_5)

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        for cite in opinion.opinions_cited.all():
            self.assertIn(cite.pk, es_doc.cites)

        # Update joined_by field in the opinion record.
        opinion.joined_by.add(self.person_3)

        es_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        for judge in opinion.joined_by.all():
            self.assertIn(judge.pk, es_doc.joined_by_ids)

        opinion.delete()

    def test_parent_document_update_fields_properly(self) -> None:
        """Confirm that parent fields are properly update when changing DB records"""
        docket = DocketFactory(
            court_id=self.court_2.pk,
        )
        opinion_cluster = OpinionClusterFactory.create(
            case_name_full="Paul test v. Franklin",
            case_name_short="Debbas",
            syllabus="some rando syllabus",
            date_filed=datetime.date(2015, 8, 14),
            procedural_history="some rando history",
            source="C",
            case_name="Debbas v. Franklin",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            precedential_status="Errata",
            citation_count=4,
            docket=docket,
        )

        # Update the court field in the docket record.
        docket.court = self.court_1
        docket.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(es_doc.court_exact, "ca1")

        # Update the absolute_url field in the cluster record.
        opinion_cluster.case_name = "Debbas v. test"
        opinion_cluster.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(
            es_doc.absolute_url,
            f"/opinion/{opinion_cluster.pk}/debbas-v-test/",
        )

        # Update the case_name_short field in the cluster record.
        opinion_cluster.case_name_short = "Franklin"
        opinion_cluster.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(es_doc.caseNameShort, "Franklin")

        # Add a new opinion to the cluster record.
        opinion_1 = OpinionFactory.create(
            extracted_by_ocr=False,
            plain_text="my plain text secret word for queries",
            cluster=opinion_cluster,
            type="020lead",
        )

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertIn(opinion_1.pk, es_doc.sibling_ids)

        opinion_2 = OpinionFactory.create(
            extracted_by_ocr=False,
            plain_text="my plain text secret word for queries",
            cluster=self.opinion_cluster_1,
            type="010combined",
        )

        opinion_2.cluster = opinion_cluster
        opinion_2.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertIn(opinion_2.pk, es_doc.sibling_ids)

        # Add a new judge to the cluster record.
        opinion_cluster.panel.add(self.person_1)

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertIn(self.person_1.pk, es_doc.panel_ids)

        # Add a new non participating judge to the cluster record.
        opinion_cluster.non_participating_judges.add(self.person_3)

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertIn(self.person_3.pk, es_doc.non_participating_judge_ids)

        # Update the scdb_id field in the cluster record.
        opinion_cluster.scdb_id = "test"
        opinion_cluster.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(es_doc.scdb_id, "test")

        # Add lexis citation to the cluster
        lexis_citation = CitationWithParentsFactory.create(
            volume=10,
            reporter="Yeates",
            page="4",
            type=6,
            cluster=opinion_cluster,
        )

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(str(lexis_citation), es_doc.lexisCite)

        # Add neutral citation to the cluster
        neutral_citation = CitationWithParentsFactory.create(
            volume=16,
            reporter="Yeates",
            page="58",
            type=8,
            cluster=opinion_cluster,
        )

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(str(neutral_citation), es_doc.neutralCite)

        # Update the source field in the cluster record.
        opinion_cluster.source = "ZLCR"
        opinion_cluster.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(es_doc.source, "ZLCR")

        # Update the cite_count field in the cluster record.
        opinion_cluster.citation_count = 8
        opinion_cluster.save()

        es_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        self.assertEqual(es_doc.citeCount, 8)

        docket.delete()
        opinion_cluster.delete()

    def test_update_shared_fields_related_documents(self) -> None:
        """Confirm that related document are properly update using bulk approach"""
        docket = DocketFactory(
            court_id=self.court_2.pk,
        )
        opinion_cluster = OpinionClusterFactory.create(
            case_name_full="Paul test v. Franklin",
            case_name_short="Debbas",
            syllabus="some rando syllabus",
            date_filed=datetime.date(2015, 8, 14),
            procedural_history="some rando history",
            source="C",
            case_name="Debbas v. Franklin",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            precedential_status="Errata",
            citation_count=4,
            docket=docket,
        )
        opinion = OpinionFactory.create(
            extracted_by_ocr=False,
            author=self.person_1,
            plain_text="my plain text secret word for queries",
            cluster=opinion_cluster,
            local_path="test/search/opinion_doc.doc",
            per_curiam=False,
            type="020lead",
        )

        # update docket number in parent document
        docket.docket_number = "005"
        docket.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.docketNumber, "005")
        self.assertEqual(opinion_doc.docketNumber, "005")

        # update the case name in the opinion cluster record
        opinion_cluster.case_name = "Debbas v. Franklin2"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.caseName, "Debbas v. Franklin2")
        self.assertEqual(opinion_doc.caseName, "Debbas v. Franklin2")

        opinion_cluster.case_name = ""
        opinion_cluster.case_name_full = "Franklin v. Debbas"
        opinion_cluster.case_name_short = "Franklin"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.caseName, "Franklin v. Debbas")
        self.assertEqual(cluster_doc.caseNameFull, "Franklin v. Debbas")
        self.assertEqual(opinion_doc.caseName, "Franklin v. Debbas")
        self.assertEqual(opinion_doc.caseNameFull, "Franklin v. Debbas")

        opinion_cluster.case_name_full = ""
        opinion_cluster.case_name_short = "Franklin50"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.caseName, "Franklin50")
        self.assertEqual(opinion_doc.caseName, "Franklin50")

        # update the date_field field in the cluster record
        opinion_cluster.date_filed = now().date()
        opinion_cluster.save()

        date_text = opinion_cluster.date_filed.strftime("%-d %B %Y")

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.dateFiled_text, date_text)
        self.assertEqual(opinion_doc.dateFiled_text, date_text)

        # update the date_argued field in the docket record
        docket.date_argued = now().date()
        docket.save()

        date_text = docket.date_argued.strftime("%-d %B %Y")

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.dateArgued_text, date_text)
        self.assertEqual(opinion_doc.dateArgued_text, date_text)

        # update the date_reargued field in the docket record
        docket.date_reargued = now().date()
        docket.save()

        date_text = docket.date_reargued.strftime("%-d %B %Y")

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.dateReargued_text, date_text)
        self.assertEqual(opinion_doc.dateReargued_text, date_text)

        # update the date_reargument_denied field in the docket record
        docket.date_reargument_denied = now().date()
        docket.save()

        date_text = docket.date_reargument_denied.strftime("%-d %B %Y")

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.dateReargumentDenied_text, date_text)
        self.assertEqual(opinion_doc.dateReargumentDenied_text, date_text)

        # update the attorneys field in the cluster record
        opinion_cluster.judges = "first judge, second judge"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.judge, "first judge, second judge")
        self.assertEqual(opinion_doc.judge, "first judge, second judge")

        # update the attorneys field in the cluster record
        opinion_cluster.attorneys = "first attorney, second attorney"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(
            cluster_doc.attorney, "first attorney, second attorney"
        )
        self.assertEqual(
            opinion_doc.attorney, "first attorney, second attorney"
        )

        # update the nature_of_suit field in the cluster record
        opinion_cluster.nature_of_suit = "test nature"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.suitNature, "test nature")
        self.assertEqual(opinion_doc.suitNature, "test nature")

        # update the precedential_status field in the cluster record
        opinion_cluster.precedential_status = "Separate"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.status, "Separate Opinion")
        self.assertEqual(opinion_doc.status, "Separate Opinion")

        # update the procedural_history field in the cluster record
        opinion_cluster.procedural_history = "random history"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.proceduralHistory, "random history")
        self.assertEqual(opinion_doc.proceduralHistory, "random history")

        # update the posture in the opinion cluster record
        opinion_cluster.posture = "random procedural posture"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.posture, "random procedural posture")
        self.assertEqual(opinion_doc.posture, "random procedural posture")

        # update the syllabus in the opinion cluster record
        opinion_cluster.syllabus = "random text for test"
        opinion_cluster.save()

        cluster_doc = OpinionClusterDocument.get(opinion_cluster.pk)
        opinion_doc = OpinionDocument.get(ES_CHILD_ID(opinion.pk).OPINION)
        self.assertEqual(cluster_doc.syllabus, "random text for test")
        self.assertEqual(opinion_doc.syllabus, "random text for test")

        docket.delete()
        opinion_cluster.delete()

    async def test_can_perform_a_regular_text_query(self) -> None:
        # Frontend
        search_params = {"q": "supreme"}
        r = await self._test_article_count(search_params, 1, "text_query")
        self.assertIn("Honda", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

        # API
        r = await self._test_api_results_count(search_params, 1, "text_query")
        self.assertIn("Honda", r.content.decode())

    async def test_homepage(self) -> None:
        """Is the homepage loaded when no GET parameters are provided?"""
        response = await self.async_client.get(reverse("show_results"))
        self.assertIn(
            'id="homepage"',
            response.content.decode(),
            msg="Did not find the #homepage id when attempting to "
            "load the homepage",
        )

    async def test_fail_gracefully(self) -> None:
        """Do we fail gracefully when an invalid search is created?"""
        response = await self.async_client.get(
            reverse("show_results"), {"filed_after": "-"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "an error",
            response.content.decode(),
            msg="Invalid search did not result in an error.",
        )

    async def test_can_search_with_white_spaces_only(self) -> None:
        """Does everything work when whitespace is in various fields?"""
        search_params = {"q": " ", "judge": " ", "case_name": " "}

        # Frontend
        r = await self._test_article_count(search_params, 4, "white_spaces")
        self.assertIn("Honda", r.content.decode())
        self.assertNotIn("an error", r.content.decode())

        # API, 2 results expected since the query shows published clusters by default
        r = await self._test_api_results_count(
            search_params, 4, "white_spaces"
        )
        self.assertIn("Honda", r.content.decode())

    async def test_can_filter_using_the_case_name(self) -> None:
        # Frontend
        search_params = {"q": "*", "case_name": "honda"}
        r = await self._test_article_count(search_params, 1, "case_name")
        self.assertIn("Honda", r.content.decode())

        # API
        r = await self._test_api_results_count(search_params, 1, "case_name")
        self.assertIn("Honda", r.content.decode())

    async def test_can_query_with_an_old_date(self) -> None:
        """Do we have any recurrent issues with old dates and strftime (issue
        220)?"""
        search_params = {"q": "*", "filed_after": "1890"}

        # Frontend
        r = await self._test_article_count(search_params, 4, "filed_after")
        self.assertEqual(200, r.status_code)

        # API
        r = await self._test_api_results_count(search_params, 4, "filed_after")
        self.assertIn("Honda", r.content.decode())

    async def test_can_filter_using_filed_range(self) -> None:
        """Does querying by date work?"""
        search_params = {
            "q": "*",
            "filed_after": "1895-06",
            "filed_before": "1896-01",
        }
        # Frontend
        r = await self._test_article_count(search_params, 1, "filed_range")
        self.assertIn("Honda", r.content.decode())

        # API
        r = await self._test_api_results_count(search_params, 1, "filed_range")
        self.assertIn("Honda", r.content.decode())

    async def test_can_filter_using_a_docket_number(self) -> None:
        """Can we query by docket number?"""
        search_params = {"q": "*", "docket_number": "2"}

        # Frontend
        r = await self._test_article_count(search_params, 1, "docket_number")
        self.assertIn(
            "Honda", r.content.decode(), "Result not found by docket number!"
        )

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket_number"
        )
        self.assertIn("Honda", r.content.decode())

    async def test_can_filter_by_citation_number(self) -> None:
        """Can we query by citation number?"""
        get_dicts = [{"q": "*", "citation": "33"}, {"q": "citation:33"}]
        for get_dict in get_dicts:
            # Frontend
            r = await self._test_article_count(get_dict, 1, "citation_count")
            self.assertIn("Honda", r.content.decode())

            # API
            r = await self._test_api_results_count(
                get_dict, 1, "citation_count"
            )
            self.assertIn("Honda", r.content.decode())

    async def test_can_filter_using_neutral_citation(self) -> None:
        """Can we query by neutral citation numbers?"""
        search_params = {"q": "*", "neutral_cite": "22"}
        # Frontend
        r = await self._test_article_count(search_params, 1, "citation_number")
        self.assertIn("Honda", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "citation_number"
        )
        self.assertIn("Honda", r.content.decode())

    async def test_can_filter_using_judge_name(self) -> None:
        """Can we query by judge name?"""
        search_array = [{"q": "*", "judge": "david"}, {"q": "judge:david"}]
        for search_params in search_array:
            # Frontend
            r = await self._test_article_count(search_params, 1, "judge_name")
            self.assertIn("Honda", r.content.decode())

            # API
            r = await self._test_api_results_count(
                search_params, 1, "judge_name"
            )
            self.assertIn("Honda", r.content.decode())

    async def test_can_filter_by_nature_of_suit(self) -> None:
        """Can we query by nature of suit?"""
        search_params = {"q": 'suitNature:"copyright"'}
        # Frontend
        r = await self._test_article_count(search_params, 1, "suit_nature")
        self.assertIn("Honda", r.content.decode())

        # API
        r = await self._test_api_results_count(search_params, 1, "suit_nature")
        self.assertIn("Honda", r.content.decode())

    async def test_can_filtering_by_citation_count(self) -> None:
        """Can we find Documents by citation filtering?"""
        search_params = {"q": "*", "cited_lt": 7, "cited_gt": 5}
        # Frontend
        r = await self._test_article_count(search_params, 1, "citation_count")
        self.assertIn(
            "Honda",
            r.content.decode(),
            msg="Did not get case back when filtering by citation count.",
        )

        # API
        r = await self._test_api_results_count(
            search_params, 1, "citation_count"
        )
        self.assertIn("Honda", r.content.decode())

        search_params = {"q": "*", "cited_lt": 100, "cited_gt": 80}
        # Frontend
        r = await self._test_article_count(search_params, 0, "citation_count")
        self.assertIn(
            "had no results",
            r.content.decode(),
            msg="Got case back when filtering by crazy citation count.",
        )

        # API
        r = self._test_api_results_count(search_params, 0, "citation_count")

    async def test_faceted_queries(self) -> None:
        """Does querying in a given court return the document? Does querying
        the wrong facets exclude it?
        """
        r = await self.async_client.get(
            reverse("show_results"), {"q": "*", "court_test": "on"}
        )
        self.assertIn("Honda", r.content.decode())

        r = await self.async_client.get(
            reverse("show_results"), {"q": "*", "stat_Errata": "on"}
        )
        self.assertNotIn("Honda", r.content.decode())
        self.assertIn("Debbas", r.content.decode())

    async def test_citation_ordering_by_citation_count(self) -> None:
        """Can the results be re-ordered by citation count?"""
        search_params = {"q": "*", "order_by": "citeCount desc"}
        most_cited_name = "case name cluster 3"
        less_cited_name = "Howard v. Honda"

        # Frontend
        r = await self._test_article_count(search_params, 4, "citeCount desc")
        self.assertTrue(
            r.content.decode().index(most_cited_name)
            < r.content.decode().index(less_cited_name),
            msg="'%s' should come BEFORE '%s' when ordered by descending "
            "citeCount." % (most_cited_name, less_cited_name),
        )
        # API
        r = await self._test_api_results_count(
            search_params, 4, "citeCount desc"
        )
        self.assertTrue(
            r.content.decode().index(most_cited_name)
            < r.content.decode().index(less_cited_name),
            msg="'%s' should come BEFORE '%s' when ordered by descending "
            "citeCount." % (most_cited_name, less_cited_name),
        )

        search_params = {"q": "*", "order_by": "citeCount asc"}
        # Frontend
        r = await self._test_article_count(search_params, 4, "citeCount asc")
        self.assertTrue(
            r.content.decode().index(most_cited_name)
            > r.content.decode().index(less_cited_name),
            msg="'%s' should come AFTER '%s' when ordered by ascending "
            "citeCount." % (most_cited_name, less_cited_name),
        )

        # API
        r = await self._test_api_results_count(
            search_params, 4, "citeCount asc"
        )
        self.assertTrue(
            r.content.decode().index(most_cited_name)
            > r.content.decode().index(less_cited_name),
            msg="'%s' should come AFTER '%s' when ordered by ascending "
            "citeCount." % (most_cited_name, less_cited_name),
        )

    async def test_random_ordering(self) -> None:
        """Can the results be ordered randomly?

        This test is difficult since we can't check that things actually get
        ordered randomly, but we can at least make sure the query succeeds.
        """
        search_params = {"q": "*", "order_by": "random_123 desc"}
        # Frontend
        r = await self._test_article_count(
            search_params, 4, "order random desc"
        )
        self.assertNotIn("an error", r.content.decode())

        # API
        await self._test_api_results_count(search_params, 4, "order random")

    async def test_issue_635_leading_zeros(self) -> None:
        """Do queries with leading zeros work equal to ones without?"""
        search_params = {"docket_number": "005", "stat_Errata": "on"}
        expected = 1
        # Frontend
        await self._test_article_count(
            search_params, expected, "docket_number"
        )

        # API
        await self._test_article_count(
            search_params, expected, "docket_number"
        )

        search_params["docket_number"] = "5"
        # Frontend
        await self._test_api_results_count(
            search_params, expected, "docket_number"
        )

        # API
        await self._test_article_count(
            search_params, expected, "docket_number"
        )

    async def test_issue_1193_docket_numbers_as_phrase(self) -> None:
        """Are docket numbers searched as a phrase?"""
        # Search for the full docket number. Does it work?
        search_params = {
            "docket_number": "docket number 1 005",
            "stat_Errata": "on",
        }
        # Frontend
        await self._test_article_count(search_params, 1, "docket_number")
        # API
        await self._test_article_count(search_params, 1, "docket_number")

        # Twist up the docket numbers. Do we get no results?
        search_params["docket_number"] = "docket 005 number"
        # Frontend
        await self._test_article_count(search_params, 0, "docket_number")
        # API
        await self._test_article_count(search_params, 0, "docket_number")

    async def test_issue_1296_abnormal_citation_type_queries(self) -> None:
        """Does search work OK when there are supra, id, or non-opinion
        citations in the query?
        """
        params = (
            {"type": SEARCH_TYPES.OPINION, "q": "42 U.S.C. § ·1383a(a)(3)(A)"},
            {"type": SEARCH_TYPES.OPINION, "q": "supra, at 22"},
        )
        for param in params:
            r = await self.async_client.get(reverse("show_results"), param)
            self.assertEqual(
                r.status_code,
                HTTP_200_OK,
                msg=f"Didn't get good status code with params: {param}",
            )

    async def test_can_render_unicode_o_character(self) -> None:
        """Does unicode HTML unicode is properly rendered in search results?"""
        r = await self.async_client.get(
            reverse("show_results"), {"q": "*", "case_name": "Washington"}
        )
        self.assertIn("Code, §", r.content.decode())

    async def test_can_use_docket_number_proximity(self) -> None:
        """Test docket_number proximity query, so that docket numbers like
        1:21-cv-1234 can be matched by queries like: 21-1234
        """

        # Query 21-1234, return results for 1:21-bk-1234
        search_params = {"type": SEARCH_TYPES.OPINION, "q": "21-1234"}
        # Frontend
        r = await self._test_article_count(
            search_params, 1, "docket number proximity"
        )
        self.assertIn("Washington", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket number proximity"
        )
        self.assertIn("Washington", r.content.decode())

        # Query 1:21-cv-1234
        search_params["q"] = "1:21-cv-1234"
        # Frontend
        r = await self._test_article_count(
            search_params, 1, "docket number proximity"
        )
        self.assertIn("Washington", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket number proximity"
        )
        self.assertIn("Washington", r.content.decode())

        # docket_number box filter: 21-1234, return results for 1:21-bk-1234
        search_params = {
            "type": SEARCH_TYPES.OPINION,
            "docket_number": "21-1234",
        }
        # Frontend
        r = await self._test_article_count(
            search_params, 1, "docket number box"
        )
        self.assertIn("Washington", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket number proximity"
        )
        self.assertIn("Washington", r.content.decode())

    async def test_can_filter_with_docket_number_suffixes(self) -> None:
        """Test docket_number with suffixes can be found."""

        # Indexed: 1:21-cv-1234 -> Search: 1:21-cv-1234-ABC
        # Frontend
        search_params = {
            "type": SEARCH_TYPES.OPINION,
            "q": f"1:21-cv-1234-ABC",
        }
        # Frontend
        r = await self._test_article_count(
            search_params, 1, "docket number box"
        )
        self.assertIn("Washington", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket number box"
        )
        self.assertIn("Washington", r.content.decode())

        # Other kind of formats can still be searched -> 123456
        search_params = {
            "type": SEARCH_TYPES.OPINION,
            "q": "123456",
        }
        # Frontend
        r = await self._test_article_count(
            search_params, 1, "docket number box"
        )
        self.assertIn("Lorem", r.content.decode())

        # API
        r = await self._test_api_results_count(
            search_params, 1, "docket number box"
        )
        self.assertIn("Lorem", r.content.decode())

    async def test_can_use_intersection_in_query(self) -> None:
        """Does AND queries work"""
        search_params = {"q": "Howard AND Honda"}
        r = await self._test_article_count(
            search_params, 1, "intersection query"
        )
        self.assertIn("Howard", r.content.decode())
        self.assertIn("Honda", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

    async def test_can_use_union_query(self) -> None:
        """Does OR queries work"""
        search_params = {"q": "Howard OR Lissner"}
        r = await self._test_article_count(search_params, 2, "union query")
        self.assertIn("Howard", r.content.decode())
        self.assertIn("Lissner", r.content.decode())
        self.assertIn("2 Opinions", r.content.decode())

    async def test_can_use_negation_in_queries(self) -> None:
        """Does negation query work"""
        search_params = {"q": "Howard"}
        r = await self._test_article_count(search_params, 1, "simple query")
        self.assertIn("Howard", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

        search_params["q"] = "Howard NOT Honda"
        r = await self._test_article_count(search_params, 0, "negation query")
        self.assertIn("had no results", r.content.decode())

        search_params["q"] = "Howard !Honda"
        r = await self._test_article_count(search_params, 0, "negation query")
        self.assertIn("had no results", r.content.decode())

        search_params["q"] = "Howard -Honda"
        r = await self._test_article_count(search_params, 0, "negation query")
        self.assertIn("had no results", r.content.decode())

    async def test_can_use_phrases_to_query(self) -> None:
        """Can we query by phrase"""
        search_params = {"q": '"Harvey Howard v. Antonin Honda"'}
        r = await self._test_article_count(search_params, 1, "phrases query")
        self.assertIn("Harvey Howard", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

        search_params["q"] = '"Antonin Honda v. Harvey Howard"'
        r = await self._test_article_count(search_params, 0, "phrases query")
        self.assertIn("had no results", r.content.decode())

    async def test_can_use_grouped_and_sub_queries(self) -> None:
        """Does grouped and sub queries work"""
        search_params = {"q": "(Lissner OR Honda) AND Howard"}
        r = await self._test_article_count(search_params, 1, "grouped query")
        self.assertIn("Howard", r.content.decode())
        self.assertIn("Honda", r.content.decode())
        self.assertIn("Lissner", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

    async def test_query_fielded(self) -> None:
        """Does fielded queries work"""
        search_params = {"q": "status:precedential"}
        r = await self._test_article_count(search_params, 4, "status")
        self.assertIn("docket number 2", r.content.decode())
        self.assertIn("docket number 3", r.content.decode())
        self.assertIn("4 Opinions", r.content.decode())

    async def test_a_wildcard_query(self) -> None:
        """Does a wildcard query work"""
        search_params = {"q": "Was*"}
        r = await self._test_article_count(search_params, 1, "wildcard query")
        self.assertIn("Strickland", r.content.decode())
        self.assertIn("Washington", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

        search_params["q"] = "?ash*"
        r = await self._test_article_count(search_params, 1, "wildcard query")
        self.assertIn("21-cv-1234", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

    async def test_a_fuzzy_query(self) -> None:
        """Does a fuzzy query work"""
        search_params = {"q": "ond~"}
        r = await self._test_article_count(search_params, 4, "fuzzy query")
        self.assertIn("docket number 2", r.content.decode())
        self.assertIn("docket number 3", r.content.decode())
        self.assertIn("4 Opinions", r.content.decode())

    async def test_proximity_query(self) -> None:
        """Does a proximity query work"""
        search_params = {"q": '"Testing Court"~3'}
        r = await self._test_article_count(search_params, 1, "proximity query")
        self.assertIn("docket number 2", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

    async def test_can_filter_using_citation_range(self) -> None:
        """Does a range query work"""
        search_params = {"q": "citation:([22 TO 33])"}
        r = await self._test_article_count(
            search_params, 2, "citation range query"
        )
        self.assertIn("docket number 2", r.content.decode())
        self.assertIn("docket number 3", r.content.decode())
        self.assertIn("2 Opinions", r.content.decode())

    async def test_can_filter_using_date_ranges(self) -> None:
        """Does a date query work"""
        search_params = {
            "q": "dateFiled:[2015-01-01T00:00:00Z TO 2015-12-31T00:00:00Z]"
        }
        r = await self._test_article_count(
            search_params, 1, "citation range query"
        )
        self.assertIn("docket number 3", r.content.decode())
        self.assertIn("1 Opinion", r.content.decode())

        search_params[
            "q"
        ] = "dateFiled:[1895-01-01T00:00:00Z TO 2015-12-31T00:00:00Z]"
        r = await self._test_article_count(
            search_params, 2, "citation range query"
        )
        self.assertIn("docket number 2", r.content.decode())
        self.assertIn("docket number 3", r.content.decode())
        self.assertIn("2 Opinions", r.content.decode())

    async def test_results_api_fields(self) -> None:
        """Confirm fields in RECAP Search API results."""
        search_params = {"q": "Honda"}
        # API
        r = await self._test_api_results_count(search_params, 1, "API fields")
        keys_to_check = [
            "absolute_url",
            "attorney",
            "author_id",
            "caseName",
            "caseNameShort",
            "citation",
            "citeCount",
            "cites",
            "cluster_id",
            "court",
            "court_citation_string",
            "court_exact",
            "court_id",
            "dateArgued",
            "dateFiled",
            "dateReargued",
            "dateReargumentDenied",
            "docketNumber",
            "docket_id",
            "download_url",
            "id",
            "joined_by_ids",
            "judge",
            "lexisCite",
            "local_path",
            "neutralCite",
            "non_participating_judge_ids",
            "panel_ids",
            "per_curiam",
            "scdb_id",
            "sibling_ids",
            "snippet",
            "source",
            "status",
            "status_exact",
            "suitNature",
            "timestamp",
            "type",
        ]
        keys_count = len(r.data["results"][0])
        self.assertEqual(keys_count, len(keys_to_check))
        for key in keys_to_check:
            self.assertTrue(
                key in r.data["results"][0],
                msg=f"Key {key} not found in the result object.",
            )

    async def test_results_highlights(self) -> None:
        """Confirm highlights are shown properly"""

        # Highlight case name.
        params = {"q": "'Howard v. Honda'"}

        r = await self._test_article_count(params, 1, "highlights case name")
        self.assertIn("<mark>Howard</mark>", r.content.decode())
        self.assertEqual(r.content.decode().count("<mark>Howard</mark>"), 1)

        self.assertIn("<mark>Honda</mark>", r.content.decode())
        self.assertEqual(r.content.decode().count("<mark>Honda</mark>"), 1)


class RelatedSearchTest(
    ESIndexTestCase, CourtTestCase, PeopleTestCase, SearchTestCase, TestCase
):
    def setUp(self) -> None:
        # Do this in two steps to avoid triggering profile creation signal
        admin = UserProfileWithParentsFactory.create(
            user__username="admin",
            user__password=make_password("password"),
        )
        admin.user.is_superuser = True
        admin.user.is_staff = True
        admin.user.save()

        super(RelatedSearchTest, self).setUp()

    def get_article_count(self, r):
        """Get the article count in a query response"""
        return len(html.fromstring(r.content.decode()).xpath("//article"))

    def test_more_like_this_opinion(self) -> None:
        """Does the MoreLikeThis query return the correct number and order of
        articles."""
        seed_pk = self.opinion_1.pk  # Paul Debbas v. Franklin
        expected_article_count = 3
        expected_first_pk = self.opinion_cluster_2.pk  # Howard v. Honda
        expected_second_pk = self.opinion_cluster_3.pk  # case name cluster 3

        params = {
            "type": "o",
            "q": "related:%i" % seed_pk,
        }

        # disable all status filters (otherwise results do not match detail page)
        params.update(
            {f"stat_{v}": "on" for s, v in PRECEDENTIAL_STATUS.NAMES}
        )

        r = self.client.get(reverse("show_results"), params)
        self.assertEqual(r.status_code, HTTP_200_OK)

        self.assertEqual(expected_article_count, self.get_article_count(r))
        self.assertTrue(
            r.content.decode().index("/opinion/%i/" % expected_first_pk)
            < r.content.decode().index("/opinion/%i/" % expected_second_pk),
            msg="'Howard v. Honda' should come AFTER 'case name cluster 3'.",
        )

    async def test_more_like_this_opinion_detail_detail(self) -> None:
        """MoreLikeThis query on opinion detail page with status filter"""
        seed_pk = self.opinion_cluster_3.pk  # case name cluster 3

        # Login as staff user (related items are by default disabled for guests)
        self.assertTrue(
            await sync_to_async(self.async_client.login)(
                username="admin", password="password"
            )
        )

        r = await self.async_client.get("/opinion/%i/asdf/" % seed_pk)
        self.assertEqual(r.status_code, 200)

        tree = html.fromstring(r.content.decode())

        recomendations_actual = [
            (a.get("href"), a.text_content().strip())
            for a in tree.xpath("//*[@id='recommendations']/ul/li/a")
        ]

        recommendations_expected = [
            (
                f"/opinion/{self.opinion_cluster_2.pk}/{self.opinion_cluster_2.slug}/?",
                "Howard v. Honda",
            ),
            (
                f"/opinion/{self.opinion_cluster_1.pk}/{self.opinion_cluster_1.slug}/?",
                "Debbas v. Franklin",
            ),
        ]

        # Test if related opinion exist in expected order
        self.assertEqual(
            recommendations_expected,
            recomendations_actual,
            msg="Unexpected opinion recommendations.",
        )

        await sync_to_async(self.async_client.logout)()

    @override_settings(RELATED_FILTER_BY_STATUS=None)
    async def test_more_like_this_opinion_detail_no_filter(self) -> None:
        """MoreLikeThis query on opinion detail page (without filter)"""
        seed_pk = self.opinion_cluster_1.pk  # Paul Debbas v. Franklin

        # Login as staff user (related items are by default disabled for guests)
        self.assertTrue(
            await sync_to_async(self.async_client.login)(
                username="admin", password="password"
            )
        )

        r = await self.async_client.get("/opinion/%i/asdf/" % seed_pk)
        self.assertEqual(r.status_code, 200)

        tree = html.fromstring(r.content.decode())

        recomendations_actual = [
            (a.get("href"), a.text_content().strip())
            for a in tree.xpath("//*[@id='recommendations']/ul/li/a")
        ]

        recommendations_expected = [
            (
                f"/opinion/{self.opinion_cluster_2.pk}/{self.opinion_cluster_2.slug}/?",
                "Howard v. Honda",
            ),
            (
                f"/opinion/{self.opinion_cluster_3.pk}/{self.opinion_cluster_3.slug}/?",
                "case name cluster 3",
            ),
        ]

        # Test if related opinion exist in expected order
        self.assertEqual(
            recommendations_expected,
            recomendations_actual,
            msg="Unexpected opinion recommendations.",
        )

        await sync_to_async(self.async_client.logout)()


class GroupedSearchTest(EmptySolrTestCase):
    @classmethod
    def setUpTestData(cls):
        court = CourtFactory(id="ca1", jurisdiction="F")

        docket = DocketFactory.create(
            date_reargument_denied=datetime.date(2015, 8, 15),
            date_reargued=datetime.date(2015, 8, 15),
            court_id=court.pk,
            case_name_full="Voutila v. Bonvini",
            date_argued=datetime.date(2015, 8, 15),
            case_name="case name docket 10",
            case_name_short="short name for Voutila v. Bonvini",
            docket_number="1337-np",
            slug="case-name",
            pacer_case_id="666666",
            blocked=False,
            source=0,
            date_blocked=None,
        )

        grouped_cluster = OpinionClusterFactory.create(
            case_name_full="Reference to Voutila v. Bonvini",
            case_name_short="Case name in short for Voutila v. Bonvini",
            syllabus="some rando syllabus",
            date_filed=datetime.date(2015, 12, 20),
            procedural_history="some rando history",
            source="C",
            judges="",
            case_name="Voutila v. Bonvini",
            attorneys="a bunch of crooks!",
            slug="case-name-cluster",
            precedential_status=PRECEDENTIAL_STATUS.PUBLISHED,
            citation_count=1,
            posture="",
            scdb_id="",
            nature_of_suit="",
            docket=docket,
        )

        OpinionFactory.create(
            extracted_by_ocr=False,
            author=None,
            plain_text="This is a lead opinion too.",
            cluster=grouped_cluster,
            local_path="txt/2015/12/28/opinion_text.txt",
            per_curiam=False,
            type="020lead",
        )

        OpinionFactory.create(
            extracted_by_ocr=False,
            author=None,
            plain_text="This is a combined opinion.",
            cluster=grouped_cluster,
            local_path="doc/2005/05/04/state_of_indiana_v._charles_barker.doc",
            per_curiam=False,
            type="010combined",
        )
        super().setUpTestData()

    def setUp(self) -> None:
        # Set up some handy variables
        super(GroupedSearchTest, self).setUp()
        args = [
            "--type",
            "search.Opinion",
            "--solr-url",
            f"{settings.SOLR_HOST}/solr/{self.core_name_opinion}",
            "--update",
            "--everything",
            "--do-commit",
            "--noinput",
        ]
        call_command("cl_update_index", *args)
        self.factory = AsyncRequestFactory()

    def test_grouped_queries(self) -> None:
        """When we have a cluster with multiple opinions, do results get
        grouped?
        """
        request = self.factory.get(reverse("show_results"), {"q": "Voutila"})
        response = do_search(request.GET.copy())
        result_count = response["results"].object_list.result.numFound
        num_expected = 1
        self.assertEqual(
            result_count,
            num_expected,
            msg="Found %s items, but should have found %s if the items were "
            "grouped properly." % (result_count, num_expected),
        )
