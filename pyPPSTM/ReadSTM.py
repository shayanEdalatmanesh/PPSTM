#!/usr/bin/python

import os
import numpy as np
import basUtils as bU
import elements


# this library has functions for reading STM coefficients and make a grid for non-relaxed 3D scan

# global variables:

cut_at_ =-1
pbc_ = (0,0)

lower_atoms_ = []
lower_coefs_ = []
cut_min_ = -15.0
cut_max_ = 5.0

n_min_ = 0
n_max_ = 0
Ynum_ = 4
num_at_ = -1

# ==============================
# ============================== Pure python functions
# ==============================


def mkSpaceGrid(xmin,xmax,dx,ymin,ymax,dy,zmin,zmax,dz):
	'''
	mkSpaceGridsxmin,xmax,dx,ymin,ymax,dy,zmin,zmax,dz):
	Give rectangular grid along the main cartesian axes for non-relaxed dI/dV or STM - 4D grid of xyz coordinates.
		'''
	h = np.mgrid[xmin:xmax+0.0001:dx,ymin:ymax+0.0001:dy,zmin:zmax+0.0001:dz]
	f = np.transpose(h)
	sh = f.shape
	print "Grid has dimensios: ", sh
	return f;	#, sh;

# preparing procedures:

def initial_check(orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lower_atoms=[], lower_coefs=[]):
	'''
	do some initial checks of incoming parameters (orbs, imaginary) and most of the global parameters for reading procedures
	'''
	assert ((orbs == 'sp')or(orbs == 'spd')), "sorry I can't do different orbitals" 
	assert (imaginary == False), "sorry imaginary version is under development" 	
	print "reading FHI-AIMS LCAO coefficients for basis: ",orbs	
	global cut_at_ ; cut_at_ = cut_at
	global pbc_    ; pbc_ = pbc
	global cut_min_ ; cut_min_ = cut_min
	global cut_max_ ; cut_max_ = cut_max
	global Ynum_    ; Ynum_ = 4 if (orbs =='sp') else 9
	global lower_atoms_ ; lower_atoms_ = lower_atoms
	global lower_coefs_ ; lower_coefs_ = lower_coefs	

# geometries underprocedures: 

def cut_atoms(atoms):
	'''
	Cut unwanted atoms !!! from the end of the geometry !!! important atoms should be first
	'''
	assert (cut_at_ <= len(atoms[1])), "wrong cut for atoms"
	if not ((cut_at_ == -1)or(cut_at_ == len(atoms[1]))):
		atoms2 = [atoms[0][:cut_at_],atoms[1][:cut_at_],atoms[2][:cut_at_],atoms[3][:cut_at_]]
	else:
		atoms2 = atoms
	global num_at_ ; num_at_= len(atoms2[1])
	return atoms2;

def for_PBC(atoms,lvs):
	'''
	Apply PBC onto the geometry
	'''
	if (pbc_ != ((0,0)or(0.,0.))):
		assert (lvs != (None or []) ), "Lattice vectors (cell) not specified"
		print "Applying PBC"
		if (pbc_ == (0.5,0.5)):
			atoms = bU.multCell( atoms, lvs, m=(2,2,1) )
			Rs = np.array([atoms[1],atoms[2],atoms[3]])
		else:
			atoms = bU.multCell( atoms, lvs, m=( (int(2*pbc_[0])+1),(int(2*pbc_[1])+1),1 ) )
			Rs = np.array([atoms[1],atoms[2],atoms[3]]); 
			Rs[0] -= int(pbc_[0])*lvs[0,0]+int(pbc_[1])*lvs[1,0]
			Rs[1] -= int(pbc_[0])*lvs[0,1]+int(pbc_[1])*lvs[1,1]
		print " Number of atoms after PBC: ", len(Rs[0])
	else:
		Rs = np.array([atoms[1],atoms[2],atoms[3]])
	Ratin    = np.transpose(Rs).copy()
	return Ratin

# procedures for preparing geometries for STM:

def get_FIREBALL_geom(geom='answer.bas', lvs=None):
	'''
	Prepares geometry from the FIREBALL files format
	'''
	print " # ============ define atoms ============"
	atoms, nDim, tmp = bU.loadAtoms(geom)
	del nDim, tmp
	atoms = cut_atoms(atoms)
	print " Number of atoms: ", num_at_
	Ratin = for_PBC(atoms,lvs)
	print "atomic geometry read"
	return Ratin ;

def get_AIMS_geom(geom='geometry.in'):
	'''
	Prepares geometry from the FHI-AIMS files format
	'''
	print " # ============ define atoms ============"
	atoms, nDim, lvs = bU.loadGeometryIN(geom)
	lvs = np.array(lvs)
	del nDim
	atoms = cut_atoms(atoms)
	at_num = []
	for i in atoms[0]:
		at_num.append(elements.ELEMENT_DICT[i][0])
	print " Number of atoms: ", num_at_
	Ratin = for_PBC(atoms,lvs)
	print "atomic geometry read"
	return Ratin, np.array(at_num);

def get_GPAW_geom(geom=None):
	'''
	Prepares geometry from the ASE atoms binary
	'''
	print " # ============ define atoms ============"
	from ase import Atoms
	tmp = geom.get_positions()
	atoms = [geom.get_atomic_numbers(), tmp[:,0], tmp[:,1], tmp[:,2] ]
	lvs = geom.get_cell()
	del tmp
	atoms = cut_atoms(atoms)
	print " Number of atoms: ", num_at_
	Ratin = for_PBC(atoms,lvs)
	print "atomic geometry read"
	return Ratin ;

# procedures for sorting eigenstates:

def to_fermi(eig, fermi, orig_fermi=0.0):
	'''
	Shift the fermi level & shift the eigenenergy to the Fermi-Level
	'''
	fermi = orig_fermi if (fermi == None) else fermi + orig_fermi
	print "The Fermi Level: ", fermi, " eV; in FHI-AIMS is the Fermi automatically 0."
	eig -= fermi
	return eig;

def cut_eigenenergies(eig):
	'''
	Removes eigenstates (molecular orbitals) that are far from the energy important for scanning
	'''	
	j = 1
	global n_min_ , n_max_
	for i in eig:
		n_min_ = j if (i < cut_min_ ) else n_min_
		n_max_ = j if (i < cut_max_ ) else n_max_
		j += 1
	assert (n_min_ < n_max_), "no orbitals left for dI/dV"
	return eig[n_min_:n_max_];

# procedure for handling the coefficients:

def lower_Allorb(coef):
	'''
	Lowering hoppings for some atoms predefined by user
	'''
	if (lower_atoms_ != []):
		print 'lowering atoms hoppings for atoms:', lower_atoms_
		i_coef = 0;
		for j in lower_atoms_:
			coef[:,j,:] *= lower_coefs_[i_coef]
			i_coef +=1
	return coef;

def lower_Dorb(coef):
	'''
	Lowering hoppings for all d-orbitals (automatically); It has physical reason, but simple rescalling is nasty
	'''
	d_rescale=0.2
	if (Ynum_ > 4): #(orbs=='spd')
		print "!!! Be aware d-orbs are now rescaled by factor of" ,d_rescale 
		print "This is due to a faster decay of d-orbs in the original basis sets, but simple rescaling is nasty !!!"
		coef[:,0,4:] *= d_rescale
	coeff = coef.flatten()
	return coeff.reshape((n_max_-n_min_,num_at_*Ynum_));

def remove_coeffs(coeffs):
	'''
	Removing the LCAO coefficients for cutted atoms
	'''
	if (cut_at_ != -1):
		coeffs=np.delete(coeffs,range(cut_at_*Ynum_,num_at_*Ynum_),1)
		global num_at_; num_at_ = cut_at_
	return coeffs;
	
def pbc_coef(coeffs):
	'''
	Applying PBC to the LCAO Coefficients
	'''
	if ((pbc_ != (0,0))or(pbc_ != (0.0,0.0))) :
		print "applying pbc"
		coeff =np.repeat(coeffs,int(pbc_[0]*2+1)*int(pbc_[1]*2+1),0).flatten()
		global num_at_;	num_at_ *=int(pbc_[0]*2+1)*int(pbc_[1]*2+1)
		coeffs = coeff.reshape((n_max_-n_min_,num_at_*Ynum_))
	return coeffs;

def	handle_coef(coef):
	'''
	Do all the necessary procedures - rescalling (user & d-orbs), cutting and applying PBC
	'''
	coef = lower_Allorb(coef)
	coeffs = lower_Dorb(coef)
	coeffs = remove_coeffs(coeffs)
	return pbc_coef(coeffs);

# procedures for preparing everything for STM:

def	read_AIMS_all(name = 'KS_eigenvectors.band_1.kpt_1.out', geom='geometry.in', fermi=None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lower_atoms=[], lower_coefs=[]):
	'''
	read_AIMS_all(name = 'KS_eigenvectors.band_1.kpt_1.out', geom='geometry.in', fermi=None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lower_atoms=[], lower_coefs=[]):
	read eigen energies, coffecients (0=Fermi Level) from the 'name' file and geometry  from the 'geom' file.
	orbs - 'sp' read only sp structure of valence orbitals or 'spd' orbitals of the sample
	Fermi - set to zero by AIMS itself
	pbc (1,1) - means 3 times 3 cell around the original, (0,0) cluster, (0.5,0.5) 2x2 cell etc.
	imaginary = False (other options for future k-points dependency
	cut_min = -15.0, cut_max = 5.0 - cut off states(=mol  orbitals) bellow cut_min and above cut_max; energy in eV
	cut_at = -1 .. all atoms; eg. cut_at = 15 --> only first fifteen atoms for the current calculations (mostly the 1st layer is the important one)
	lower_atotms=[], lower_coefs=[] ... do nothing; lower_atoms=[0,1,2,3], lower_coefs=[0.5,0.5,0.5,0.5] lower coefficients (=hoppings) for the first four atoms by 0.5
	header - newer version of aims gives one aditional line with AIMS-UUID to the output files
	'''
	initial_check(orbs=orbs, pbc=pbc, imaginary=imaginary, cut_min=cut_min, cut_max=cut_max, cut_at=cut_at, lower_atoms=lower_atoms, lower_coefs=lower_coefs)
	# obtaining the geometry :
	Ratin, at_num = get_AIMS_geom(geom=geom)
	#print "at_num:",at_num

	# getting eigen-energies:
	filein = open(name )
	skip_header = 2
	for i in range(20):
		tmp=filein.readline().split()
		skip_header += 1
		if (len(tmp)>1):
			if (tmp[1]=='Basis'):
				break
	tmp=filein.readline()
	pre_eig = filein.readline().split()
	filein.close()
	pre_eig=np.delete(pre_eig,[0,1,2],0)
	n_bands = len(pre_eig)
	eig = np.zeros(n_bands)
	for i in range(n_bands):
		eig[i] = float(pre_eig[i])
	del pre_eig, tmp;
	eig = to_fermi(eig, fermi, orig_fermi=0.0)
	eig = cut_eigenenergies(eig)
	print "eigenenergies read"
	
	# finding position of the LCAO coeficients in the AIMS output file & its phase - sign
	tmp = np.genfromtxt(name,skip_header=skip_header, usecols=(1,2,3,4,5),dtype=None)
	orb_pos=np.zeros((num_at_,Ynum_), dtype=np.int)
	orb_sign=np.zeros((num_at_,Ynum_), dtype=np.int)
	orb_pos += -1
	el = elements.ELEMENTS
	for j in range(num_at_):
		Z = at_num[j];
		per = el[Z][2]
		temp=int((np.mod(2,2)-0.5)*2)	# phase of radial function in long distance for l=0: if n even - +1, if odd - -1
		if (orbs == 'sp'):
			orb_sign[j]=[temp,-1*temp,-1*temp,temp]		# {1, 1, 1, -1};(*Dont change, means - +s, +py +pz -px*) but l=1 has opposite phase than l=0 ==>  sign[s]*{1, -1, -1, 1};
		else: # (orbs == 'spd'):
			orb_sign[j]=[temp,-1*temp,-1*temp,temp,-1*temp,-1*temp,-1*temp,temp,-1*temp]		# {1, 1, 1, -1, 1, 1, 1, 1, -1, 1};(*Dont change, means - +s, +py +pz -px +dxy +dyz +dz2 -dxz +dx2y2)
			# but l=1 has opposite phase than l=0 and l=2 is n-1 - the same phase as l=1 ==>  sign[s]*{1, -1, -1, 1, -1, -1, -1, 1, -1};
	for i in range(len(tmp)):
		for j in range(num_at_):
			Z = at_num[j];
			per = el[Z][2]
			if ((tmp[i][0]==j+1)and(tmp[i][1]=='atomic')):
				if (tmp[i][2]==per):
					if 	(tmp[i][3]=='s'):
						orb_pos[j,0]=i
					elif (tmp[i][3]=='p'):
						if  (tmp[i][4]==-1):
							orb_pos[j,1]=i
						elif (tmp[i][4]==0):
							orb_pos[j,2]=i
						elif (tmp[i][4]==1):
							orb_pos[j,3]=i
				elif ((tmp[i][2]==per-1)and(orbs=='spd')and(per>3)):
					if (tmp[i][3]=='d'):
						if   (tmp[i][4]==-2):
							orb_pos[j,4]=i
						elif (tmp[i][4]==-1):
							orb_pos[j,5]=i
						elif (tmp[i][4]==0):
							orb_pos[j,6]=i
						elif (tmp[i][4]==1):
							orb_pos[j,7]=i
						elif (tmp[i][4]==2):
							orb_pos[j,8]=i
	# Reading the coefficients and assigning proper sign, just for wanted eigen-energies
	print "The main reading procedure, it can take some time, numpy reading txt can be slow."
	del tmp; del temp;
	tmp = np.genfromtxt(name,skip_header=skip_header, usecols=tuple(xrange(6, n_bands*2+6, 2))) #tmp = np.genfromtxt(name,skip_header=5)#, usecols=(6,))
	tmp = tmp[:,n_min_:n_max_]
	coef = np.zeros((n_max_-n_min_,num_at_,Ynum_))
	for j in range(num_at_):
		for l in range(Ynum_):
			if (orb_pos[j,l]!=-1):
				coef[:,j,l] = tmp[orb_pos[j,l],:]
				coef[:,j,l] *= orb_sign[j,l]
	del tmp;
	# lowering over atoms and applying PBC
	coeffs = handle_coef(coef)
	print "All coefficients read"
	return eig.copy(), coeffs.copy(), Ratin.copy();

def	read_GPAW_all(name = 'OUTPUT.gpw', fermi = None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lower_atoms=[], lower_coefs=[] ):
	'''
	read_GPAW_all(name = 'OUTPUT.gpw', fermi = None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lower_atoms=[], lower_coefs=[]):
	This procedure nead to import ASE and GPAW
	read eigen energies, coffecients, Fermi Level and geometry  from the GPAW  *.gpw file.
	If fermi = None then Fermi comes from the GPAW calculation
	orbs - only 'sp' works 	can read only sp structure of valence orbitals (hydrogens_has to be at the end !!!!)
	pbc (1,1) - means 3 times 3 cell around the original, (0,0) cluster, (0.5,0.5) 2x2 cell etc.
	imaginary = False (other options for future k-points dependency
	cut_min = -15.0, cut_max = 5.0 - cut off states(=mol  orbitals) bellow cut_min and above cut_max; energy in eV
	cut_at = -1 .. all atoms; eg. cut_at = 15 --> only first fifteen atoms for the current calculations (mostly the 1st layer is the important one)
	lower_atotms=[], lower_coefs=[] ... do nothing; lower_atoms=[0,1,2,3], lower_coefs=[0.5,0.5,0.5,0.5] lower coefficients (=hoppings) for the first four atoms by 0.5
	'''
	initial_check(orbs=orbs, pbc=pbc, imaginary=imaginary, cut_min=cut_min, cut_max=cut_max, cut_at=cut_at, lower_atoms=lower_atoms, lower_coefs=lower_coefs)
	# obtaining the geometry :
	from ase import Atoms
	from gpaw import GPAW
	calc = GPAW(name)
	slab = calc.get_atoms()
	Ratin = get_GPAW_geom(geom=slab)

	# getting eigen-energies
	n_bands = calc.get_number_of_bands()
	eig = calc.get_eigenvalues(kpt=0, spin=0, broadcast=True)
	at_num = slab.get_atomic_numbers()
	eig = to_fermi(eig, fermi, orig_fermi=calc.get_fermi_level())
	eig = cut_eigenenergies(eig)
	print "eigen-energies read"
	# obtaining the LCAO coefficients (automatically removed unwanted states - molecular orbitals - and atoms)
	coef = np.zeros((n_max_-n_min_,num_at_,Ynum_))
	if (orbs=='spd'):
		print "!!! WARNING: d-orbitals should be in principle working, but coefficients can be wrong, according to my experiences !!!"
		print "DEBUG: going to crazy procedure, which finds, where the d-orbs starts"
		print "from gpaw.utilities.dos import print_projectors; print_projectors('X')"
		print "this prints you where the d-orb should start"
		from gpaw.setup_data import SetupData
		chem_sym=slab.get_chemical_symbols()
		d_orb=np.zeros((num_at_));
		for i in range(num_at_):
			if at_num[i]>2:
				setup =  SetupData(chem_sym[i],'LDA','paw');l_j = setup.l_j;tmp=l_j[:l_j.index(2)];a=[1,3];oo=0;
				for j in range(len(tmp)):
					oo +=a[tmp[j]];
				d_orb[i]=oo;
	for i in range(n_min_,n_max_):
		h=0
		for j in range(num_at_):
			ii = i-n_min_
			coef[ii,j,0] = calc.wfs.kpt_u[0].C_nM[i,h]
			if (at_num[j]>2):
				coef[ii,j,1] = calc.wfs.kpt_u[0].C_nM[i,h+1]
				coef[ii,j,2] = calc.wfs.kpt_u[0].C_nM[i,h+2]
				coef[ii,j,3] = calc.wfs.kpt_u[0].C_nM[i,h+3]
				if ((orbs=='spd')and(d_orb[j]>1)):
					coef[ii,j,4] = calc.wfs.kpt_u[0].C_nM[i,h+d_orb[j]]
					coef[ii,j,5] = calc.wfs.kpt_u[0].C_nM[i,h+d_orb[j]+1]
					coef[ii,j,6] = calc.wfs.kpt_u[0].C_nM[i,h+d_orb[j]+2]
					coef[ii,j,7] = calc.wfs.kpt_u[0].C_nM[i,h+d_orb[j]+3]
					coef[ii,j,8] = calc.wfs.kpt_u[0].C_nM[i,h+d_orb[j]+4]
			h += calc.wfs.setups[j].nao
	#from gpaw.utilities.dos import print_projectors; print_projectors('Cu')
	#print "DEBUG: Cu coeffs:"
	#for i in range(n_min,n_max):
	#	for j in range(15):
	#		print j, calc.wfs.kpt_u[0].C_nM[i,j]
	#	print "DEBUG: coef[sth,0,:]" , coef[i-n_min,0,:] 
	# lowering tunneling for predefined atoms
	# lowering over atoms and applying PBC
	coeffs = handle_coef(coef)
	print "All coefficients read"
	return eig.copy(), coeffs.copy(), Ratin.copy();

def	read_FIREBALL_all(name = 'phi_' , geom='answer.bas', fermi=None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lvs = None, lower_atoms=[], lower_coefs=[]):
	'''
	read_FIREBALL_all(name = 'phi_' , geom='answer.bas', fermi=None, orbs = 'sp', pbc=(1,1), imaginary = False, cut_min=-15.0, cut_max=5.0, cut_at=-1, lvs = None, lower_atoms=[], lower_coefs=[]):
	This procedure uses only local libraries;
	read coffecients and eigen numbers from Fireball made (iwrtcoefs = -2) files phik_0001_s.dat, phik_0001_py.dat ....
	fermi - If None the Fermi Level from the Fireball calculations (in case of molecule and visualising some molecular orbitals it can be move to their energy by putting there real value)
	orbs = 'sp' read only sp structure of valence orbitals or 'spd' orbitals of the sample
	pbc (1,1) - means 3 times 3 cell around the original, (0,0) cluster, (0.5,0.5) 2x2 cell etc.
	imaginary = False (other options for future k-points dependency
	cut_min = -15.0, cut_max = 5.0 - cut off states(=mol  orbitals) bellow cut_min and above cut_max; energy in eV
	cut_at = -1 .. all atoms; eg. cut_at = 15 --> only first fifteen atoms for the current calculations (mostly the 1st layer is the important one)
	lvs = None no lattice vector (cell); for PBC 3x3 array containing the cell vectors has to be put here
	lower_atotms=[], lower_coefs=[] ... do nothing; lower_atoms=[0,1,2,3], lower_coefs=[0.5,0.5,0.5,0.5] lower coefficients (=hoppings) for the first four atoms by 0.5
	note: sometimes oxygens have to have hoppings lowered by 0.5 this is under investigation
	'''
	initial_check(orbs=orbs, pbc=pbc, imaginary=imaginary, cut_min=cut_min, cut_max=cut_max, cut_at=cut_at, lower_atoms=lower_atoms, lower_coefs=lower_coefs)
	# obtaining the geometry :
	Ratin = get_FIREBALL_geom(geom=geom, lvs=lvs)

	# getting eigen-energies
	filein = open(name+'s.dat' )
	pre_eig = filein.readline().split()
	filein.close()
	assert (num_at_>int(pre_eig[0][0])),"coefficients for lower amount of atoms, that atoms in geometry file";
	n_bands= int(pre_eig[1]);
	eig = np.loadtxt(name+'s.dat',skiprows=1, usecols=(0,))
	assert (len(eig)==n_bands), "number of bands wrongly specified"
	eig = to_fermi(eig, fermi, orig_fermi=float(pre_eig[2]))
	del pre_eig;
	eig = cut_eigenenergies(eig)
	print "eigen-energies read"

	print " loading the LCAO coefficients"
	coef = np.zeros((n_bands,num_at_,Ynum_))
	if (num_at_ > 1):
		coef[:,:,0] = np.loadtxt(name+'s.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,:,1] = np.loadtxt(name+'py.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,:,2] = np.loadtxt(name+'pz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,:,3] = np.loadtxt(name+'px.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		if (orbs =='spd'):
			coef[:,:,4] = np.loadtxt(name+'dxy.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,:,5] = np.loadtxt(name+'dyz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,:,6] = np.loadtxt(name+'dz2.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,:,7] = np.loadtxt(name+'dxz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,:,8] = np.loadtxt(name+'dx2y2.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
	else:
		coef[:,0,0] = np.loadtxt(name+'s.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,0,1] = np.loadtxt(name+'py.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,0,2] = np.loadtxt(name+'pz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		coef[:,0,3] = np.loadtxt(name+'px.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
		if (orbs =='spd'):
			coef[:,0,4] = np.loadtxt(name+'dxy.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,0,5] = np.loadtxt(name+'dyz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,0,6] = np.loadtxt(name+'dz2.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,0,7] = np.loadtxt(name+'dxz.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )
			coef[:,0,8] = np.loadtxt(name+'dx2y2.dat',skiprows=1,usecols=tuple(xrange(1, num_at_*2+1, 2)) )

	# removing states (molecular orbitals) that are not wanted
	coef=coef[n_min_:n_max_,:,:]
	# lowering over atoms and applying PBC
	coeffs = handle_coef(coef)
	print "All coefficients read"
	return eig.copy(), coeffs.copy(), Ratin.copy();

############## END OF LIBRARY ##################################
