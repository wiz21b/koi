from sqlalchemy import event

from koi.business_charts import NonConformityInternal, DirectIndirectEvolutionChart, DoneVsPlannedHoursOnCompletedParts, \
    NonConformityCustomer, DeadlinDeliveryChartOTD, OQDChart, OrderPartsValue, PreOrderPartsValue, \
    NumberOfCreatedOrderParts, NumberOfCustomerWhoOrdered, IndirectWorkEvolutionChart, ToBillThisMonth, \
    ValuationThisMonth, TurnOverThisMonth, RunningValuationChart, ToFacturePerMonthChart, DirectWorkCostEvolutionChart, \
    SoldeCarnetCommande, DirectWorkEvolutionChart, EstimatedVersusActualTimePerMonthChart
from koi.gui.indicators_panel import IndicatorsPanel
from koi.service_config import remote_documents_service, remote_indicators_service
from koi.db_mapping import TimeTrack, DeliverySlipPart
from koi.datalayer.employee_mapping import RoleType


class ISOIndicatorsWidget(IndicatorsPanel):

    def __init__(self,parent, remote_indicators_service):
        super(ISOIndicatorsWidget,self).__init__(parent, remote_indicators_service, _("ISO indicators overview"),
             [
                 [_("Production"),
                  NonConformityInternal(None, remote_indicators_service),
                  DirectIndirectEvolutionChart(None, remote_indicators_service),
                  DoneVsPlannedHoursOnCompletedParts(None,
                                                     remote_indicators_service),
                  NonConformityCustomer(None, remote_indicators_service),
                  DeadlinDeliveryChartOTD(None, remote_indicators_service),
                  OQDChart(None, remote_indicators_service)
                  ],
                 [_("Commercial"),
                  OrderPartsValue(None, remote_indicators_service),
                  PreOrderPartsValue(None, remote_indicators_service),
                  NumberOfCreatedOrderParts(None, remote_indicators_service),
                  NumberOfCustomerWhoOrdered(None, remote_indicators_service),
                  # SoldeCarnetCommande(None,remote_indicators_service), # very slow !
                  # EvolutionEncours(None,remote_indicators_service), # very slow !
                  IndirectWorkEvolutionChart(None, remote_indicators_service, mini=0, maxi=100000)
                  # useless, just for testing
                  ]
             ] )


class FinancialIndicatorsWidget(IndicatorsPanel):

    def __init__(self,parent, remote_indicators_service):
        super(FinancialIndicatorsWidget,self).__init__(parent, remote_indicators_service,
                                                       _("Global financial overview"),
             [
                 [
                     _("Financial values for %MONTH%"),
                     [
                         ["",
                          ToBillThisMonth(None, remote_indicators_service),
                          ValuationThisMonth(None, remote_indicators_service)],
                         ["",
                          TurnOverThisMonth(None, remote_indicators_service)]
                     ],

                     RunningValuationChart(None, remote_indicators_service),
                     SoldeCarnetCommande(None, remote_indicators_service),
                     # ValuationLastMonth(None, remote_indicators_service),
                 ],
                 [
                    _("Trends"),
                    ToFacturePerMonthChart(None, remote_indicators_service),
                    DirectWorkCostEvolutionChart(None, remote_indicators_service, mini=0, maxi=100000),
                    IndirectWorkEvolutionChart(None, remote_indicators_service, mini=0, maxi=100000),
                 ],
             ] )


class MonthlyProductionReportOverviewWidget(IndicatorsPanel):

    def __init__(self,parent, remote_indicators_service):
        super(MonthlyProductionReportOverviewWidget, self).__init__(parent, remote_indicators_service, _("Global production overview"),
             [
                 [
                     "",
                     DirectIndirectEvolutionChart(None, remote_indicators_service),
                     DirectWorkEvolutionChart(None, remote_indicators_service, mini=0, maxi=100)
                 ],
                 [
                    "",
                    DeadlinDeliveryChartOTD(None, remote_indicators_service),
                    EstimatedVersusActualTimePerMonthChart(None, remote_indicators_service)
                 ],
             ] )



class KoiModuleBase:
    def wire(self, koi_base):
        pass

class IndicatorsModule(KoiModuleBase):
    def __init__(self):
        global remote_indicators_service

        parent = None
        self.iso_panel = ISOIndicatorsWidget( parent, remote_indicators_service)
        self.financial_panel = FinancialIndicatorsWidget( parent, remote_indicators_service)
        self.production_panel = MonthlyProductionReportOverviewWidget( parent, remote_indicators_service)

    def _data_changed(self, mapper, connection, target):
        self.financial_panel.refresh_panel()
        self.production_panel.refresh_panel()

    def wire(self, koi_base):
        """
        Method called on instanciation of the module. Normally this is done
        once at the beginng of the execution.

        This is called after all module instances and all services have been
        instanciated (but not necessearliy wired).

        :param koi_base:
        :return:
        """

        koi_base.register_instance(self.production_panel, "ProductionKPIPanel")
        koi_base.register_instance(self.iso_panel, "ISOKPIPanel")
        koi_base.register_instance(self.financial_panel, "FinancialKPIPanel")

        koi_base.add_menu_item("/main_menu/production", "ProductionKPIPanel")
        koi_base.add_menu_item("/main_menu/production", "ISOKPIPanel")
        koi_base.add_menu_item("/main_menu/production", "FinancialKPIPanel", roles=[RoleType.view_financial_information])

        # Connect to database events
        event.listen(TimeTrack,        'after_insert', self._data_changed)
        event.listen(DeliverySlipPart, 'after_insert', self._data_changed)

