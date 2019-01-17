from datetime import date

if __name__ == "__main__":
    from koi.base_logging import init_logging
    from koi.Configurator import init_i18n,load_configuration,configuration

    init_logging()
    init_i18n()
    load_configuration()

    from koi.db_mapping import metadata
    from koi.datalayer.database_session import init_db_session

    init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

if __name__ != "__main__":
    from koi.datalayer.serializers import *
else:
    from koi.datalayer.serializers import *

from sqlalchemy.sql.expression import desc
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

from koi.base_logging import mainlog
from koi.db_mapping import Customer
from koi.datalayer.database_session import session
from koi.dao import dao
from koi.session.UserSession import user_session



FAST_LOAD_ARTICLE_CONFIGURATIONS  = session().query(ArticleConfiguration).\
        options(
            joinedload(ArticleConfiguration.part_plan),
            joinedload(ArticleConfiguration.customer),
            joinedload(ArticleConfiguration.impacts),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.document),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.owner),
            joinedload(ArticleConfiguration.impacts).joinedload(ImpactLine.approved_by),
            joinedload(ArticleConfiguration.configurations),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.parts),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.freezer),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.lines),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.lines).joinedload(ConfigurationLine.document),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.document),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.owner),
            joinedload(ArticleConfiguration.configurations).joinedload(Configuration.origins).joinedload(ImpactLine.approved_by))


class ConfigurationManagementService:

    def __init__(self):
        pass

    def unfreeze_configuration(self, config : CopyConfiguration):
        # One can only unfreeze he last config (that's not as flexible as one might want
        # but thtat'll be enough for now

        sqla_c = session().query(Configuration).filter( Configuration.configuration_id == config.configuration_id).one()

        assert sqla_c.frozen is not None, "Can't unfreeze a configuration that is not frozen"
        assert len(sqla_c.parts) == 0, "There are parts wired to this configuration"

        sqla_c.frozen = None # Indicate it's not frozen anymore.
        sqla_c.freezer = None

        session().commit()

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla_c.article_configuration, None, dict())
        session().commit()
        return r


    def freeze_configuration( self, config : CopyConfiguration):

        # By construction, all the existing configurations are correct as far
        # as impact documents are concerned. So we just need to verify
        # the existence of impact document for safety purposes.

        # To be able to use a configuration, it must be frozen. And to be able
        # to freeze a configuration, it must contains at least on impact document.
        # Therefore, to be able to use a configuration article, one has to make
        # sure it has at least one impact document.

        # Now an exception has to be made for the baseline configuration. This one
        # comes to existence from a plan/plan revision. So there's no need for an
        # impact document to freeze it.

        sqla_c = session().query(Configuration).filter( Configuration.configuration_id == config.configuration_id).one()

        # The last config is the one I want to freeze

        assert sqla_c.frozen == None, "Can't freeze a config th is already frozen"
        assert len(sqla_c.lines) >= 1, "Can't freeze an empty configuration"

        sqla_c.frozen = date.today()
        sqla_c.freezer = user_session.employee()

        if not sqla_c.is_baseline:
            # Base line config doesn't require impact document to be frozen.
            # Others do.

            impact_docs_ok = False
            for impact_doc in sqla_c.article_configuration.impacts:
                if impact_doc.configuration == sqla_c:
                    impact_docs_ok = True

            assert impact_docs_ok, "Somehow, we're missing an impact document"

        # # When we freeze, we automatically add a new version

        # c = Configuration()
        # session().add(c)
        # c.frozen = None
        # c.version = max([c.version for c in sqla_ac.configurations]) + 1
        # sqla_ac.configurations.append( c)
        # session().commit()

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla_c.article_configuration, None, dict())
        session().commit()
        return r



    def edit_item( self, ac : CopyArticleConfiguration):

        article_configuration_id = ac.article_configuration_id

        sqla_ac = session().query(ArticleConfiguration).filter( ArticleConfiguration.article_configuration_id == article_configuration_id).one()

        pyxfer_cache = dict()
        with session().no_autoflush:
            sqla = serialize_ArticleConfiguration_CopyArticleConfiguration_to_ArticleConfiguration( ac, sqla_ac, session(), pyxfer_cache)
            session().flush()
        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla, None, dict())
        session().commit()
        return r

    def track_new_item( self, ac : CopyArticleConfiguration):
        pyxfer_cache = dict()
        with session().no_autoflush:
            sqla = serialize_ArticleConfiguration_CopyArticleConfiguration_to_ArticleConfiguration( ac, None, session(), pyxfer_cache)
            session().flush()

        baseline_config = Configuration()
        session().add( baseline_config)
        sqla.configurations.append( baseline_config)
        session().flush()

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla, None, dict())
        session().commit()
        return r

    def search_configuration_articles( self, key : str):
        if not key:
            r = FAST_LOAD_ARTICLE_CONFIGURATIONS.filter().order_by( desc( ArticleConfiguration.date_creation))[0:100]
        else:
            r = FAST_LOAD_ARTICLE_CONFIGURATIONS.join(Customer).filter(
                or_( ArticleConfiguration.identification_number.like( "%{}%".format(key)),
                     Customer.fullname.like( "%{}%".format(key)))).order_by( desc( ArticleConfiguration.date_creation))[0:100]
            # r = FAST_LOAD_ARTICLE_CONFIGURATIONS.filter( ArticleConfiguration.identification_number.like( "%{}%".format(key))).order_by( desc( ArticleConfiguration.date_creation))[0:100]

        # FIXME performance issue here : too much eager loading I think. I need to make a serializer
        # that just picks the dispalyed column and then another loader that works one demand.
        result = [ serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla, None, dict()) for sqla in r]

        session().commit()
        return result

    def add_document_to_configuration( self, document : CopyConfigurationLine):
        # The impact document will be added to the configuration article it refers to.
        # One can add one or more impact documents a to aconfiguration.

        assert document
        assert not document.configuration_line_id, "Document was already added"
        assert document.configuration_id, "The document must be added to an existing configuration"

        with session().no_autoflush:
            sqla_config_line = serialize_ConfigurationLine_CopyConfigurationLine_to_ConfigurationLine( document, None, session(), dict())
            session().flush()

        # I return article cofniguration instead of impact line because the client
        # side will need to update more on the screen than just this very new impact line.
        # moreover, this allow to simplify the client which doesn't have to fiddle
        # with reconnecting varioous objects together

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla_config_line.configuration.article_configuration, None, dict())
        session().commit()
        return r

    def add_impact_document( self, impact : CopyImpactLine):
        # The impact document will be added to the configuration article it refers to.
        # One can add one or more impact documents a to aconfiguration.

        assert impact
        assert not impact.impact_line_id, "Impact document was already be created"
        assert impact.article_configuration_id, "The impact document must belong to an existing configuration article"

        with session().no_autoflush:
            sqla_impact = serialize_ImpactLine_CopyImpactLine_to_ImpactLine( impact, None, session(), dict())
            session().flush()

        # I return article cofniguration instead of impact line because the client
        # side will need to update more on the screen than just this very new impact line.
        # moreover, this allow to simplify the client which doesn't have to fiddle
        # with reconnecting varioous objects together

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla_impact.article_configuration, None, dict())
        session().commit()
        return r


    def add_configuration_revision( self, ac_id : int, impact_documents_ids):
        """ Add a configuration revision to a tracked configuration item.
        The creation must be justified by at least one impact
        document.
        """
        assert impact_documents_ids, "Configuration revision must be wired to at least one impact document"

        sqla_ac = session().query(ArticleConfiguration).filter(ArticleConfiguration.article_configuration_id == ac_id).one()
        impact_documents = session().query(ImpactLine).filter( ImpactLine.impact_line_id.in_( impact_documents_ids)).all()

        for impact in impact_documents:
            assert impact.configuration_id is None and not impact.configuration, "Impact documents must not be already in use for other revisions"

        if len(sqla_ac.configurations) > 1:
            assert sqla_ac.configurations[-1].frozen, "You can add a new revision only if the previous one is frozen"


        c = Configuration()
        session().add(c)

        existing_versions = [c.version for c in sqla_ac.configurations]
        if existing_versions:
            c.version = max( existing_versions) + 1
        else:
            c.version = 1

        c.article_configuration = sqla_ac
        sqla_ac.configurations.append(c)

        for impact in impact_documents:
            #impact.configuration_id = c.configuration_id
            impact.configuration = c

        session().flush()

        r = serialize_ArticleConfiguration_ArticleConfiguration_to_CopyArticleConfiguration( sqla_ac, None, dict())
        session().commit()
        return r




configuration_management_service = ConfigurationManagementService()

if __name__ == "__main__":

    print("hello")

    r = configuration_management_service.search_configuration_articles("SYS")
    print(len(r))
    r = configuration_management_service.search_configuration_articles(None)
    print(len(r))

    customer = session().query(Customer).first()

    ac = CopyArticleConfiguration()
    ac.customer_id = customer.customer_id

    cnt = session().query(ArticleConfiguration).count()
    assert ac.article_configuration_id is None

    ac = configuration_management_service.track_new_item( ac)

    assert cnt + 1 == session().query(ArticleConfiguration).count()
    assert ac.article_configuration_id is not None
    assert len(ac.customer.fullname) >= 1
