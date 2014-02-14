import os 
import WEM.utils as utils

class Lazy:
    def __init__(self,config):
        self.C = config
    
    def go(self,casestr,IC,experiment,ensnames):
        """
        Inputs: (all folder names)
        casestr     :   string of case study initialisation date/time
        IC          :   initial condition model
        experiment  :   dictionary. Key: ensemble type (ICBC,STCH,MXMP)
                            -initial condition/boundary condition 
                            -stochastic kinetic energy backscatter
                            -mixed model parameterisations
                        Value...
                            -model configuration (CTRL) for ICBC
                            -initial condition model/ens member for others
        ensnames    :   list of ensemble member names
                            - e.g. c00,p01,p02
                            
        """
        self.casestr = casestr
        self.IC = IC
        self.experiment = experiment.keys()
        self.control = ensemble.values()
        self.ensnames = ensnames
        
        self.GO = {'GEFSR2':go_GEFS,'NAMANL':go_NAMANL,
                   'NAMFCST':go_NAMFCST, 'GFSANL':go_GFSANL,
                   'GFSFCST':go_GFSFCST'}
        
                    
        """
        self.enstype is a list of ensemble models or types.
        self.enslist is a list of each model's member names.
        Both are used to name runs, and folders for output etc
        
        Lookup table GO contains the methods to run for each 
        ensemble type.
        """
        
        GO[IC](self.ensnames)
        
    def go_GEFSR2(self,ensns):    
        
        """ 
        Runs WPS, WRF for one set of initial conditions
        and settings based on the GEFSR2 model.
        
        Inputs:
        ensns   :   names of ensemble member
        """
        for n,e in ensns:
            # e is the next ensemble member to run
            if n==0:
                run_exe('geogrid.exe')
    
                # Soil data
                copy_namelist('wps')
                edit_namelist('wps',"prefix"," prefix = 'SOIL'")
                link_to_soil_data()
                link_to_soil_Vtable()
                run_exe('ungrib.exe')
                
                # Atmos data
                edit_namelist("prefix"," prefix = 'GEFSR2'")
                link_to_IC_data('GEFSR2')
                link_to_IC_Vtable('GEFSR2')
                run_exe('ungrib.exe')
                
                # Combine both intermediate files
                edit_namelist("fg_name"," fg_name = 'SOIL','GEFSR2'")
                run_exe('metgrid.exe')

                submit_job()

                to_folder = os.path.join(self.casestr,'GEFSR2',e,self.experiment)
                copy_files(to_folder)      
                os.system('rm -f rsl.error* rsl.out*')
                
                
    def copy_files(self,tofolder):
        """ 
        Move wrfout* files to folder.
        Create folder if it doesn't exist

        Move *.TS files if they exist
        Copy namelist.input to that folder.
        Copy rsl.error.0000 to the folder.
        
        Input(s):
        args = names of folder tree, in order of depth.
        """
        root = self.C.path_to_storage
        topath = os.path.join(root,tofolder)
        
        utils.trycreate(topath)
        
        files = {'wrfout_d0*':'mv','namelist.input':'cp',
                    'rsl.error.0000':'cp'}

        if len(glob.glob('*.TS')):
            # hi-res time series files
            files['*.TS'] = 'mv'
            files['tslist'] = 'cp'
        
        for f,transfer in files.iteritems:
            fs = os.path.join(self.C.path_to_WRF,f)
            command = '{0} {1} {2}'.format(transfer,fs,topath)
            os.system(command)
            del command


    def submit_job(self):
        # Soft link data netCDFs files from WPS to WRF
        link_to_met_em()
        
        print("Submitting real.exe.")
        real_cmd = 'qsub -d {0} real_run.sh'.format(self.C.path_to_WRF)
        p_real = subprocess.Popen(real_cmd,cwd=self.C.path_to_WRF,shell=True,stdout=subprocess.PIPE)
        p_real.wait()
        jobid = p_real.stdout.read()[:5] # Assuming first five digits = job ID.
        
        # Run WRF but wait until real.exe has finished without errors
        print 'Now submitting wrf.exe.'
        wrf_cmd = 'qsub -d {0} wrf_run.sh -W depend=afterok:{1}'.format(
                        self.C.path_to_WRF,jobid)
        p_wrf = subprocess.Popen(wrf_cmd,cwd=pathtoWRF,shell=True)
        p_wrf.wait()

        time.sleep(self.C.roughguesshr*60*60) # Wait specified hours
        
        # Makes sure real.exe has finished and wrf.exe is writing to rsl files
        finished = 0
        while not finished:
            path_to_rsl = os.path.join(self.C.path_to_WRF,'rsl.error.0000')
            tail_cmd = 'tail {0}'.format(path_to_rsl)
            tailrsl = subprocess.Popen(tail_cmd,shell=True,stdout=subprocess.PIPE)
            tailoutput = tailrsl.stdout.read()
            if "SUCCESS COMPLETE WRF" in tailoutput:
                finished = 1
                print "WRF has finished; moving to next case."
            else:
                time.sleep(5*60) # Try again in 5 min
        
    def link_to_met_em(self):
        path_to_met_em = os.path.join(self.C.path_to_WPS,'met_em*')
        command = 'ln -sf {0} {1}'.format(path_to_met_em,self.C.path_to_WRF)
        os.system(command)
             
    def link_to_IC_data(self,IC,*args):
        """
        Inputs:
        *args   :   e.g. ensemble member
        """
        if IC == 'GEFSR2':
            """
            Assumes files are within a folder named casestr (YYYYMMDD)
            """
            csh = './link_grib.csh'
            gribfiles = '_'.join((self.casestr,nextens,'f*')
            gribpath = os.path.join(self.C.path_to_GEFSR2,gribfiles)
            command = ' '.join(csh,gribpath)
        
        os.system(command)

    def link_to_IC_Vtable(self,IC):
        if IC == 'GEFSR2':
            path = os.path.join(self.C.path_to_WPS,'ungrib/Variable_Tables',
                            self.C.GEFSR2_Vtable)
            command = 'ln -sf {0} Vtable'.format(path)
        
        os.system(command)

    def link_to_soil_data(self):
        csh = './link_grib.csh'
        command = ' '.join(csh,self.C.path_to_soil)
        os.system(command)
        
    def link_to_soil_Vtable(self):
        path = os.path.join(self.C.path_to_WPS,'ungrib/Variable_Tables',
                            self.C.soil_Vtable)
        command = 'ln -sf {0} Vtable'.format(path)
        os.system(command)
        
    def edit_namelist(self,suffix,sett,newval,maxdom=1):
        """ Method edits namelist.wps or namelist.input.
        
        Inputs:
        suffix  :   which namelist needs changing
        sett    :   setting that needs changing
        newval  :   its new value -> currently replaces whole line
        maxdom  :   number of domains to edit
                    (this is relevant for multiple columns?)
                    
        No outputs, just changes the file.
        """
        if suffix == 'wps':
            f = os.path.join(self.self.C.path_to_WPS,'namelist.wps')
        elif suffix == 'input:
            f = os.path.join(self.self.C.path_to_WRF,'namelist.input')
        flines = open(f,'r').readlines()
        for idx, line in enumerate(flines):
            if sett in line:
                # Prefix for soil intermediate data filename
                flines[idx] = newval + " \n"
                nameout = open(f,'w')
                nameout.writelines(flines)
                nameout.close()
                break
            
    def run_exe(self,exe):
        """Run WPS executables, then check to see if it failed.
        If not, return True to proceed.
        
        Input:
        exe     :   .exe file name.
        """
        
        #if not exe.endswith('.exe'):
        #    f,suffix = exe.split('.')            
        
        command = os.path.join('./',self.C.path_to_WPS,exe)
        os.system(command)
        
        # Wait until complete, then check tail file
        name,suffix = exe.split('.')
        log = name + '.log'
        l = open(name+'.log','r').readlines()
        lastline = l[-1]
        if 'Successful completion' in lastline:
            pass
            #return True
        else:
            print ('Running {0} has failed. Check {1}.'.format(
                        exe,log)
            raise SomethingIsBrokenException

        def generate_date(self,date,outstyle='wps'):
            """ Creates date string for namelist files.
            
            Input:
            """
            pass
        
        def copy_namelist(self,suffix):
            """Appends current time to namelist to create backup.
            """
            t = time.strftime("%Y%m%d_%H%M")
            if suffix == 'wps':
                f = os.path.join(path_to_WPS,'namelist.wps') # Original 
            elif suffix == 'input':
                f = os.path.join(path_to_WRF,'namelist.input') # Original    
                
            f2 = '_'.join((f,t)) # Backup file
            command = ' '.join(('cp',f,f2))
            print("Backed up namelist.{0}.".format(suffix))
            
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                