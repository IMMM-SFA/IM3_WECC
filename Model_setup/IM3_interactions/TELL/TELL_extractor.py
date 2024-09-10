# -*- coding: utf-8 -*-
"""
Created on Sun Nov  6 11:58:38 2022

@author: kakdemi
"""

import pandas as pd
import numpy as np
import os
from shutil import copy
from pathlib import Path
import sys

def TELL_extract(NN,UC,T_p,BA_hurd,YY,Hydro_year,TELL_year,CS,CERF_year,TELL_year_scaled):
    
    #Correcting the directory
    cwd = os.getcwd()
    os.chdir("{}\\TELL".format(cwd[:-4]))
    
    #Creating artifical time series for filtering
    hours_2015 = pd.date_range(start='01-01-2015 00:00:00', end='12-31-2015 23:00:00', freq='h')
    
    #Reading TELL outputs and BA information
    if TELL_year < 2020:
        TELL_outputs_df = pd.read_csv('TELL_outputs/historic/TELL_Balancing_Authority_Hourly_Load_Data_{}_Scaled_{}.zip'.format(TELL_year,TELL_year_scaled),header=0)
        TELL_outputs_df_next = pd.read_csv('TELL_outputs/historic/TELL_Balancing_Authority_Hourly_Load_Data_{}_Scaled_{}.zip'.format(TELL_year+1,TELL_year_scaled+1),header=0) #Reading next year's dataset to change time zone from UTC to PST
    else:
        TELL_outputs_df = pd.read_csv('TELL_outputs/{}/TELL_Balancing_Authority_Hourly_Load_Data_{}_Scaled_{}.zip'.format(CS,TELL_year,TELL_year_scaled),header=0)
        TELL_outputs_df_next = pd.read_csv('TELL_outputs/{}/TELL_Balancing_Authority_Hourly_Load_Data_{}_Scaled_{}.zip'.format(CS,TELL_year+1,TELL_year_scaled+1),header=0) #Reading next year's dataset to change time zone from UTC to PST
    
    df_BAs = pd.read_csv('../../../Data_setup/Time_series_data/BA_data/BAs.csv',header=0)
    GO_WEST_BAs = [*df_BAs['Abbreviation']]
    BAs = list(df_BAs['Name'])
    
    df_full = pd.read_csv('../../../Data_setup/10k_topology_files/nodes_to_BA_state.csv',header=0)
    
    #Organizing TELL outputs to get the load weights
    for i in GO_WEST_BAs:
        
        BA_index = GO_WEST_BAs.index(i)
        BA_sp_TELL_data = TELL_outputs_df.loc[TELL_outputs_df['BA_Code']==i]['Scaled_TELL_BA_Load_MWh'].values
        BA_sp_TELL_data = BA_sp_TELL_data.reshape(BA_sp_TELL_data.shape[0],1)

        BA_sp_TELL_data_next = TELL_outputs_df_next.loc[TELL_outputs_df_next['BA_Code']==i]['Scaled_TELL_BA_Load_MWh'].values
        BA_sp_TELL_data_next = BA_sp_TELL_data_next.reshape(BA_sp_TELL_data_next.shape[0],1)
        
        if BA_index == 0:
            TELL_all_BAs_load = BA_sp_TELL_data
            TELL_all_BAs_load_next = BA_sp_TELL_data_next
            
        else:
            TELL_all_BAs_load = np.hstack((TELL_all_BAs_load,BA_sp_TELL_data))
            TELL_all_BAs_load_next = np.hstack((TELL_all_BAs_load_next,BA_sp_TELL_data_next))
    
    df_load = pd.DataFrame(TELL_all_BAs_load,columns=GO_WEST_BAs)
    df_load_next = pd.DataFrame(TELL_all_BAs_load_next,columns=GO_WEST_BAs)
    
    if len(df_load) > len(hours_2015):
        diff_num_hrs = 24-(len(df_load) - len(hours_2015))
        hours_2020 = pd.date_range(start='01-01-2020 0{}:00:00'.format(diff_num_hrs), end='12-31-2020 23:00:00', freq='h')
        feb_29_hours = pd.date_range(start='2-29-2020 0{}:00:00'.format(diff_num_hrs),end='2-29-2020 23:00:00', freq='h')
        df_load.index = hours_2020
        df_load.drop(feb_29_hours,inplace=True)
        df_load.reset_index(drop=True,inplace=True) 
    else:
        pass

    if len(df_load_next) > len(hours_2015):
        diff_num_hrs = 24-(len(df_load_next) - len(hours_2015))
        hours_2020 = pd.date_range(start='01-01-2020 0{}:00:00'.format(diff_num_hrs), end='12-31-2020 23:00:00', freq='h')
        feb_29_hours = pd.date_range(start='2-29-2020 0{}:00:00'.format(diff_num_hrs),end='2-29-2020 23:00:00', freq='h')
        df_load_next.index = hours_2020
        df_load_next.drop(feb_29_hours,inplace=True)
        df_load_next.reset_index(drop=True,inplace=True) 
    else:
        pass
    
    #Creating nodal load weights and distributing loads to nodes in the system
    #Reading all selected nodes
    df_selected = pd.read_excel('../../Selected_nodes/Results_Excluded_Nodes_{}.xlsx'.format(NN),sheet_name='Bus',header=0)
    buses = list(df_selected['bus_i'])
    
    #Appending BA names column to all buses dataframe
    selected_BAs = []
    for b in buses:
        BA = df_full.loc[df_full['Number']==b,'NAME'].values[0]
        selected_BAs.append(BA)
    df_selected['BA'] = selected_BAs
        
    #Calculating nodal weights within each BA and distributing loads to each node accordingly
    BA_totals = []
    for b in BAs:
        sample = list(df_selected.loc[df_selected['BA']==b,'Pd'])
        corrected = [0 if x<0 else x for x in sample]
        BA_totals.append(sum(corrected))
    
    BA_totals = np.column_stack((BAs,BA_totals))
    df_BA_totals = pd.DataFrame(BA_totals,columns=['Name','Total'])
    
    weights = []
    for i in range(0,len(df_selected)):
        area = df_selected.loc[i,'BA']
        if df_selected.loc[i,'Pd'] <0:
            weights.append(0)
        else:        
            X = float(df_BA_totals.loc[df_BA_totals['Name']==area,'Total'].iloc[0])
            W = (df_selected.loc[i,'Pd']/X)
            weights.append(W)
    df_selected['BA Load Weight'] = weights
    
    T = np.zeros((8760,len(buses)))
    T_next = np.zeros((8760,len(buses)))
    
    for i in range(0,len(df_selected)):
        
        name = df_selected.loc[i,'BA']
        
        if float(df_BA_totals.loc[df_BA_totals['Name']==str(name),'Total'].values[0]) < 1:
            pass
        else: 
            
            abbr = df_BAs.loc[df_BAs['Name']==name,'Abbreviation'].values[0]
            weight = df_selected.loc[i,'BA Load Weight']
            
            if max(df_load[abbr]) < 1:
                T[:,i] = T[:,i] + np.reshape(df_load[abbr].values,(8760,))                    
            else:                    
                T[:,i] = T[:,i] + np.reshape(df_load[abbr].values*weight,(8760,)) 

            if max(df_load_next[abbr]) < 1:
                T_next[:,i] = T_next[:,i] + np.reshape(df_load_next[abbr].values,(8760,))                    
            else:                    
                T_next[:,i] = T_next[:,i] + np.reshape(df_load_next[abbr].values*weight,(8760,)) 

    buses_str = ['bus_{}'.format(i) for i in buses]
    
    df_C = pd.DataFrame(T,columns=buses_str)
    df_C_next = pd.DataFrame(T_next,columns=buses_str)

    #Changing timezone from UTC to PST by shifting time series by 8 hours
    Timezone_diff = 8
    combined_demand = pd.concat([df_C.loc[Timezone_diff:,:],df_C_next.loc[:Timezone_diff-1,:]], axis=0, ignore_index=True)
    
    #Exporting demand data
    combined_demand.to_csv('../Altered_simulation_folders/Exp{}{}_{}_{}_{}_{}/Inputs/nodal_load.csv'.format(NN,UC,T_p,BA_hurd,CERF_year,CS),index=None)   
    
    return None
    
    

    
    